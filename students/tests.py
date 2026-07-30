from datetime import date
from io import BytesIO
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from PIL import Image

from accounts.models import RoleChoices, TeacherProfile, UserRole
from academics.models import ClassLevel, Section
from schools.models import AcademicYear, School
from students.models import Student

User = get_user_model()


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class BoardClassEligibilityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school = School.objects.create(name="Board High School", slug="board-high")
        self.other_school = School.objects.create(name="Other School", slug="other-school")
        self.year = AcademicYear.objects.create(
            school=self.school,
            name="2026-2027",
            start_date=date(2026, 4, 1),
            end_date=date(2027, 3, 31),
            is_active=True,
        )
        self.board_class = ClassLevel.objects.create(
            school=self.school,
            academic_year=self.year,
            name="Class 9",
            order=9,
            is_board_class=True,
        )
        self.regular_class = ClassLevel.objects.create(
            school=self.school,
            academic_year=self.year,
            name="Class 5",
            order=5,
            is_board_class=False,
        )

        self.admin = self._create_user("admin@board.test", RoleChoices.SCHOOL_ADMIN)
        self.manager = self._create_user("manager@board.test", RoleChoices.MANAGER)
        self.teacher_user = self._create_user("teacher@board.test", RoleChoices.TEACHER)
        self.other_teacher_user = self._create_user("other.teacher@board.test", RoleChoices.TEACHER)

        self.teacher = TeacherProfile.objects.create(user=self.teacher_user, school=self.school)
        self.other_teacher = TeacherProfile.objects.create(user=self.other_teacher_user, school=self.school)

        self.board_section = Section.objects.create(
            school=self.school,
            class_level=self.board_class,
            name="A",
            class_teacher=self.teacher,
        )
        self.regular_section = Section.objects.create(
            school=self.school,
            class_level=self.regular_class,
            name="A",
            class_teacher=self.teacher,
        )
        self.other_section = Section.objects.create(
            school=self.school,
            class_level=self.board_class,
            name="B",
            class_teacher=self.other_teacher,
        )

        self.board_student = Student.objects.create(
            school=self.school,
            section=self.board_section,
            first_name="Ali",
            last_name="Raza",
        )
        self.regular_student = Student.objects.create(
            school=self.school,
            section=self.regular_section,
            first_name="Sara",
            last_name="Noor",
        )
        self.other_teacher_student = Student.objects.create(
            school=self.school,
            section=self.other_section,
            first_name="Hassan",
            last_name="Ali",
        )

    def _create_user(self, email: str, role: str):
        user = User.objects.create_user(email=email, password="DemoPass123!", active_school=self.school)
        UserRole.objects.create(user=user, school=self.school, role=role)
        return user

    def test_admin_can_mark_class_as_board(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.patch(
            f"/api/v1/class-levels/{self.regular_class.id}/",
            {"is_board_class": True},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.regular_class.refresh_from_db()
        self.assertTrue(self.regular_class.is_board_class)

    def test_manager_can_set_board_roll_number(self):
        self.client.force_authenticate(user=self.manager)
        response = self.client.patch(
            f"/api/v1/students/{self.board_student.id}/",
            {"board_roll_number": " 452187 "},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["board_roll_number"], "452187")
        self.assertTrue(response.data["is_board_class"])

    def test_blank_board_roll_number_allowed(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.patch(
            f"/api/v1/students/{self.board_student.id}/",
            {"board_roll_number": ""},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["board_roll_number"], "")

    def test_non_board_class_rejects_board_roll_number(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.patch(
            f"/api/v1/students/{self.regular_student.id}/",
            {"board_roll_number": "999001"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("board_roll_number", response.data)

    def test_duplicate_board_roll_number_rejected(self):
        self.client.force_authenticate(user=self.admin)
        first = self.client.patch(
            f"/api/v1/students/{self.board_student.id}/",
            {"board_roll_number": "DUP-001"},
            format="json",
        )
        self.assertEqual(first.status_code, 200)
        second = self.client.patch(
            f"/api/v1/students/{self.other_teacher_student.id}/",
            {"board_roll_number": "DUP-001"},
            format="json",
        )
        self.assertEqual(second.status_code, 400)
        self.assertIn("board_roll_number", second.data)

    def test_teacher_only_sees_assigned_section_students(self):
        self.client.force_authenticate(user=self.teacher_user)
        response = self.client.get("/api/v1/students/")
        self.assertEqual(response.status_code, 200)
        ids = {student["id"] for student in response.data["results"]}
        self.assertIn(self.board_student.id, ids)
        self.assertIn(self.regular_student.id, ids)
        self.assertNotIn(self.other_teacher_student.id, ids)

    def test_teacher_sees_students_in_multi_teacher_sections(self):
        self.other_section.teachers.add(self.teacher)
        self.client.force_authenticate(user=self.teacher_user)

        response = self.client.get("/api/v1/students/")

        self.assertEqual(response.status_code, 200)
        ids = {student["id"] for student in response.data["results"]}
        self.assertIn(self.other_teacher_student.id, ids)

    def test_teacher_can_update_board_roll_for_assigned_student(self):
        self.client.force_authenticate(user=self.teacher_user)
        response = self.client.patch(
            f"/api/v1/students/{self.board_student.id}/",
            {"board_roll_number": "TCH-9001"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["board_roll_number"], "TCH-9001")

    def test_teacher_cannot_update_other_fields(self):
        self.client.force_authenticate(user=self.teacher_user)
        response = self.client.patch(
            f"/api/v1/students/{self.board_student.id}/",
            {"first_name": "Hacked", "board_roll_number": "TCH-9002"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_teacher_cannot_access_unassigned_student(self):
        self.client.force_authenticate(user=self.teacher_user)
        response = self.client.patch(
            f"/api/v1/students/{self.other_teacher_student.id}/",
            {"board_roll_number": "NOPE"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    def test_teacher_cannot_create_students(self):
        self.client.force_authenticate(user=self.teacher_user)
        response = self.client.post(
            "/api/v1/students/",
            {"first_name": "New", "last_name": "Kid", "status": "active"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class FamilyFieldsAndParentProvisioningTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school = School.objects.create(name="Family School", slug="family-school")
        self.other_school = School.objects.create(name="Other Family School", slug="other-family")
        self.year = AcademicYear.objects.create(
            school=self.school,
            name="2026-2027",
            start_date=date(2026, 4, 1),
            end_date=date(2027, 3, 31),
            is_active=True,
        )
        self.class_level = ClassLevel.objects.create(
            school=self.school,
            academic_year=self.year,
            name="Class 1",
            order=1,
        )
        self.section = Section.objects.create(
            school=self.school,
            class_level=self.class_level,
            name="A",
        )
        self.admin = User.objects.create_user(
            email="admin@family.test",
            password="DemoPass123!",
            active_school=self.school,
        )
        UserRole.objects.create(user=self.admin, school=self.school, role=RoleChoices.SCHOOL_ADMIN)

    def test_cnic_is_normalised_and_validated(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            "/api/v1/students/",
            {
                "first_name": "Ali",
                "last_name": "Khan",
                "status": "active",
                "section": self.section.id,
                "father_cnic": "35202-1234567-1",
                "mother_cnic": "3520212345672",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["father_cnic"], "3520212345671")
        self.assertEqual(response.data["mother_cnic"], "3520212345672")

        bad = self.client.post(
            "/api/v1/students/",
            {
                "first_name": "Sara",
                "last_name": "Khan",
                "status": "active",
                "father_cnic": "12345",
            },
            format="json",
        )
        self.assertEqual(bad.status_code, 400)
        self.assertIn("father_cnic", bad.data)

    def test_siblings_can_share_cnic_and_parent_email(self):
        self.client.force_authenticate(user=self.admin)
        shared = {
            "father_cnic": "3520211111111",
            "mother_cnic": "3520222222222",
            "parent_email": "shared.parent@family.test",
            "father_name": "Imran Khan",
            "status": "active",
            "section": self.section.id,
        }
        first = self.client.post(
            "/api/v1/students/",
            {"first_name": "Child", "last_name": "One", **shared},
            format="json",
        )
        second = self.client.post(
            "/api/v1/students/",
            {"first_name": "Child", "last_name": "Two", **shared},
            format="json",
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)

        from accounts.models import ParentProfile
        from students.models import ParentStudentLink

        parent_user = User.objects.get(email="shared.parent@family.test")
        self.assertFalse(parent_user.has_usable_password())
        profile = ParentProfile.objects.get(user=parent_user)
        self.assertEqual(ParentStudentLink.objects.filter(parent=profile).count(), 2)

    def test_re_saving_student_does_not_duplicate_parent_link(self):
        self.client.force_authenticate(user=self.admin)
        created = self.client.post(
            "/api/v1/students/",
            {
                "first_name": "Only",
                "last_name": "Child",
                "status": "active",
                "parent_email": "once@family.test",
                "father_name": "Dad",
            },
            format="json",
        )
        self.assertEqual(created.status_code, 201)
        student_id = created.data["id"]
        updated = self.client.patch(
            f"/api/v1/students/{student_id}/",
            {"parent_email": "once@family.test", "region": "Lahore"},
            format="json",
        )
        self.assertEqual(updated.status_code, 200)

        from students.models import ParentStudentLink

        self.assertEqual(ParentStudentLink.objects.filter(student_id=student_id).count(), 1)

    def test_parent_email_conflict_across_schools(self):
        other_admin = User.objects.create_user(
            email="admin@other-family.test",
            password="DemoPass123!",
            active_school=self.other_school,
        )
        UserRole.objects.create(user=other_admin, school=self.other_school, role=RoleChoices.SCHOOL_ADMIN)

        other_parent = User.objects.create_user(
            email="conflict@family.test",
            password="unused",
            active_school=self.other_school,
        )
        other_parent.set_unusable_password()
        other_parent.save()
        from accounts.models import ParentProfile

        ParentProfile.objects.create(user=other_parent, school=self.other_school)

        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            "/api/v1/students/",
            {
                "first_name": "Cross",
                "last_name": "School",
                "status": "active",
                "parent_email": "conflict@family.test",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("parent_email", response.data)


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class StudentProfileImageTests(TestCase):
    def setUp(self):
        self._media_dir = tempfile.mkdtemp(prefix="students-media-")
        self._storage_override = override_settings(
            STORAGES={
                "default": {
                    "BACKEND": "django.core.files.storage.FileSystemStorage",
                    "OPTIONS": {"location": self._media_dir, "base_url": "/media/"},
                },
                "staticfiles": {
                    "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
                },
            }
        )
        self._storage_override.enable()

        self.client = APIClient()
        self.school = School.objects.create(name="Image School", slug="image-school")
        self.year = AcademicYear.objects.create(
            school=self.school,
            name="2026-2027",
            start_date=date(2026, 4, 1),
            end_date=date(2027, 3, 31),
            is_active=True,
        )
        self.class_level = ClassLevel.objects.create(
            school=self.school,
            academic_year=self.year,
            name="Class 3",
            order=3,
        )
        self.section = Section.objects.create(school=self.school, class_level=self.class_level, name="A")

        self.admin = User.objects.create_user(
            email="admin@student-image.test",
            password="DemoPass123!",
            active_school=self.school,
        )
        self.teacher_user = User.objects.create_user(
            email="teacher@student-image.test",
            password="DemoPass123!",
            active_school=self.school,
        )
        UserRole.objects.create(user=self.admin, school=self.school, role=RoleChoices.SCHOOL_ADMIN)
        UserRole.objects.create(user=self.teacher_user, school=self.school, role=RoleChoices.TEACHER)
        teacher_profile = TeacherProfile.objects.create(user=self.teacher_user, school=self.school)
        self.section.class_teacher = teacher_profile
        self.section.save(update_fields=["class_teacher"])

    def tearDown(self):
        self._storage_override.disable()
        shutil.rmtree(self._media_dir, ignore_errors=True)
        super().tearDown()

    def _image_file(self, name: str = "avatar.png", image_format: str = "PNG"):
        buffer = BytesIO()
        Image.new("RGB", (96, 96), color=(24, 120, 220)).save(buffer, format=image_format)
        return SimpleUploadedFile(name, buffer.getvalue(), content_type=f"image/{image_format.lower()}")

    def test_admin_can_upload_profile_image_on_create(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            "/api/v1/students/",
            {
                "first_name": "Adeel",
                "last_name": "Khan",
                "status": "active",
                "section": self.section.id,
                "profile_image": self._image_file(),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)
        student = Student.objects.get(pk=response.data["id"])
        self.assertTrue(student.profile_image.name.startswith("profile-images/students/school-"))
        self.assertTrue(student.profile_image.name.endswith(".webp"))
        self.assertIn(".webp", response.data["profile_image"])

    def test_invalid_profile_image_type_is_rejected(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            "/api/v1/students/",
            {
                "first_name": "Invalid",
                "status": "active",
                "section": self.section.id,
                "profile_image": SimpleUploadedFile("bad.txt", b"hello", content_type="text/plain"),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("profile_image", response.data)

    def test_oversized_profile_image_is_rejected(self):
        self.client.force_authenticate(user=self.admin)
        too_big = SimpleUploadedFile(
            "too-big.png",
            b"x" * (5 * 1024 * 1024 + 1),
            content_type="image/png",
        )
        response = self.client.post(
            "/api/v1/students/",
            {
                "first_name": "Large",
                "status": "active",
                "section": self.section.id,
                "profile_image": too_big,
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("profile_image", response.data)

    def test_replacing_profile_image_removes_old_object(self):
        self.client.force_authenticate(user=self.admin)
        created = self.client.post(
            "/api/v1/students/",
            {
                "first_name": "Replace",
                "status": "active",
                "section": self.section.id,
                "profile_image": self._image_file("first.png"),
            },
            format="multipart",
        )
        student = Student.objects.get(pk=created.data["id"])
        old_name = student.profile_image.name
        storage = student.profile_image.storage

        with self.captureOnCommitCallbacks(execute=True):
            updated = self.client.patch(
                f"/api/v1/students/{student.id}/",
                {"profile_image": self._image_file("second.png")},
                format="multipart",
            )
        self.assertEqual(updated.status_code, 200)
        student.refresh_from_db()
        self.assertNotEqual(student.profile_image.name, old_name)
        self.assertFalse(storage.exists(old_name))

    def test_clearing_profile_image_deletes_file(self):
        self.client.force_authenticate(user=self.admin)
        created = self.client.post(
            "/api/v1/students/",
            {
                "first_name": "Clear",
                "status": "active",
                "section": self.section.id,
                "profile_image": self._image_file("clear.png"),
            },
            format="multipart",
        )
        student = Student.objects.get(pk=created.data["id"])
        old_name = student.profile_image.name
        storage = student.profile_image.storage

        with self.captureOnCommitCallbacks(execute=True):
            updated = self.client.patch(
                f"/api/v1/students/{student.id}/",
                {"profile_image_clear": True},
                format="multipart",
            )
        self.assertEqual(updated.status_code, 200)
        student.refresh_from_db()
        self.assertEqual(student.profile_image.name, "")
        self.assertFalse(storage.exists(old_name))

    def test_teacher_cannot_edit_profile_image(self):
        student = Student.objects.create(
            school=self.school,
            section=self.section,
            first_name="Protected",
            last_name="Student",
        )
        self.client.force_authenticate(user=self.teacher_user)
        response = self.client.patch(
            f"/api/v1/students/{student.id}/",
            {"profile_image": self._image_file()},
            format="multipart",
        )
        self.assertEqual(response.status_code, 403)
