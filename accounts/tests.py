from datetime import date
from decimal import Decimal
from io import BytesIO
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from PIL import Image

from academics.models import ClassLevel, Section, Subject, TeacherSubjectAssignment
from accounts.models import RoleChoices, TeacherProfile, UserRole
from schools.models import AcademicYear, School

User = get_user_model()


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class TeacherEmploymentTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school = School.objects.create(name="Teacher School", slug="teacher-school")
        self.other_school = School.objects.create(name="Other Teacher School", slug="other-teacher-school")
        self.year = AcademicYear.objects.create(
            school=self.school,
            name="2026-2027",
            start_date=date(2026, 4, 1),
            end_date=date(2027, 3, 31),
            is_active=True,
        )
        self.other_year = AcademicYear.objects.create(
            school=self.other_school,
            name="2026-2027",
            start_date=date(2026, 4, 1),
            end_date=date(2027, 3, 31),
            is_active=True,
        )
        self.math = Subject.objects.create(school=self.school, name="Mathematics")
        self.english = Subject.objects.create(school=self.school, name="English")
        self.other_subject = Subject.objects.create(school=self.other_school, name="Physics")
        self.class_level = ClassLevel.objects.create(
            school=self.school,
            academic_year=self.year,
            name="Class 5",
            order=5,
        )
        self.section = Section.objects.create(school=self.school, class_level=self.class_level, name="A")

        self.admin = User.objects.create_user(
            email="admin@teacher.test",
            password="DemoPass123!",
            active_school=self.school,
        )
        UserRole.objects.create(user=self.admin, school=self.school, role=RoleChoices.SCHOOL_ADMIN)
        self.client.force_authenticate(user=self.admin)

    def test_create_teacher_with_employment_fields_and_multiple_subjects(self):
        response = self.client.post(
            "/api/v1/accounts/teachers/",
            {
                "first_name": "Sara",
                "last_name": "Ahmed",
                "email": "sara.teacher@example.com",
                "password": "DemoPass123!",
                "qualification": "MSc Mathematics",
                "monthly_salary": "85000.00",
                "address": "House 12, Model Town, Lahore",
                "cnic": "35202-1234567-1",
                "phone_number": "03001234567",
                "designation": "subject_teacher",
                "shift_start_time": "07:30:00",
                "shift_end_time": "14:30:00",
                "subjects_taught": [self.math.id, self.english.id],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["cnic"], "3520212345671")
        self.assertEqual(response.data["monthly_salary"], "85000.00")
        self.assertEqual(response.data["designation"], "subject_teacher")
        self.assertEqual(response.data["shift_start_time"], "07:30:00")
        self.assertEqual(response.data["shift_end_time"], "14:30:00")
        self.assertEqual(set(response.data["subjects_taught"]), {self.math.id, self.english.id})
        self.assertEqual(response.data["subject_names"], ["English", "Mathematics"])

    def test_all_designations_are_accepted(self):
        designations = ["subject_teacher", "accountant", "principal", "sports_teacher", "maid"]
        for index, designation in enumerate(designations):
            response = self.client.post(
                "/api/v1/accounts/teachers/",
                {
                    "first_name": designation,
                    "last_name": "Employee",
                    "email": f"{designation}.{index}@example.com",
                    "password": "DemoPass123!",
                    "designation": designation,
                },
                format="json",
            )
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.data["designation"], designation)

    def test_shift_requires_complete_valid_range(self):
        missing_end = self.client.post(
            "/api/v1/accounts/teachers/",
            {
                "first_name": "Missing",
                "last_name": "End",
                "email": "missing.end@example.com",
                "password": "DemoPass123!",
                "shift_start_time": "08:00:00",
            },
            format="json",
        )
        self.assertEqual(missing_end.status_code, 400)
        self.assertIn("shift_end_time", missing_end.data)

        backwards = self.client.post(
            "/api/v1/accounts/teachers/",
            {
                "first_name": "Wrong",
                "last_name": "Range",
                "email": "wrong.range@example.com",
                "password": "DemoPass123!",
                "shift_start_time": "15:00:00",
                "shift_end_time": "08:00:00",
            },
            format="json",
        )
        self.assertEqual(backwards.status_code, 400)
        self.assertIn("shift_end_time", backwards.data)

    def test_negative_salary_rejected(self):
        response = self.client.post(
            "/api/v1/accounts/teachers/",
            {
                "first_name": "Bad",
                "last_name": "Salary",
                "email": "bad.salary@example.com",
                "password": "DemoPass123!",
                "monthly_salary": "-100",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("monthly_salary", response.data)

    def test_duplicate_cnic_rejected(self):
        first = self.client.post(
            "/api/v1/accounts/teachers/",
            {
                "first_name": "First",
                "last_name": "Teacher",
                "email": "first.teacher@example.com",
                "password": "DemoPass123!",
                "cnic": "3520211111111",
            },
            format="json",
        )
        self.assertEqual(first.status_code, 201)
        second = self.client.post(
            "/api/v1/accounts/teachers/",
            {
                "first_name": "Second",
                "last_name": "Teacher",
                "email": "second.teacher@example.com",
                "password": "DemoPass123!",
                "cnic": "35202-1111111-1",
            },
            format="json",
        )
        self.assertEqual(second.status_code, 400)
        self.assertIn("cnic", second.data)

    def test_cross_school_subject_rejected(self):
        response = self.client.post(
            "/api/v1/accounts/teachers/",
            {
                "first_name": "Cross",
                "last_name": "School",
                "email": "cross.teacher@example.com",
                "password": "DemoPass123!",
                "subjects_taught": [self.other_subject.id],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("subjects_taught", response.data)

    def test_update_replaces_subject_specialties_without_touching_section_assignments(self):
        created = self.client.post(
            "/api/v1/accounts/teachers/",
            {
                "first_name": "Assigned",
                "last_name": "Teacher",
                "email": "assigned.teacher@example.com",
                "password": "DemoPass123!",
                "subjects_taught": [self.math.id],
            },
            format="json",
        )
        self.assertEqual(created.status_code, 201)
        teacher_id = created.data["id"]
        profile = TeacherProfile.objects.get(pk=teacher_id)
        assignment = TeacherSubjectAssignment.objects.create(
            school=self.school,
            teacher=profile,
            subject=self.math,
            section=self.section,
            academic_year=self.year,
        )

        updated = self.client.patch(
            f"/api/v1/accounts/teachers/{teacher_id}/",
            {"subjects_taught": [self.english.id]},
            format="json",
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.data["subjects_taught"], [self.english.id])
        profile.refresh_from_db()
        self.assertEqual(list(profile.subjects_taught.values_list("id", flat=True)), [self.english.id])
        self.assertTrue(TeacherSubjectAssignment.objects.filter(pk=assignment.pk).exists())

    def test_search_by_phone_number(self):
        self.client.post(
            "/api/v1/accounts/teachers/",
            {
                "first_name": "Phone",
                "last_name": "Search",
                "email": "phone.search@example.com",
                "password": "DemoPass123!",
                "phone_number": "03119998877",
            },
            format="json",
        )
        response = self.client.get("/api/v1/accounts/teachers/?search=03119998877")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)

    def test_teacher_dashboard_uses_live_assigned_section_and_student_counts(self):
        created = self.client.post(
            "/api/v1/accounts/teachers/",
            {
                "first_name": "Dashboard",
                "last_name": "Teacher",
                "email": "dashboard.teacher@example.com",
                "password": "DemoPass123!",
                "subjects_taught": [self.math.id, self.english.id],
            },
            format="json",
        )
        self.assertEqual(created.status_code, 201)
        profile = TeacherProfile.objects.get(pk=created.data["id"])
        teacher_user = profile.user

        second_section = Section.objects.create(
            school=self.school,
            class_level=self.class_level,
            name="B",
        )
        self.section.teachers.add(profile)
        second_section.teachers.add(profile)

        from students.models import Student

        Student.objects.create(
            school=self.school,
            section=self.section,
            first_name="Student",
            last_name="One",
        )
        Student.objects.create(
            school=self.school,
            section=second_section,
            first_name="Student",
            last_name="Two",
        )

        self.client.force_authenticate(user=teacher_user)
        response = self.client.get("/api/v1/accounts/teacher-dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["assigned_sections"], 2)
        self.assertEqual(response.data["students"], 2)
        self.assertEqual(response.data["subjects"], 2)
        self.assertEqual(response.data["incharge_sections"], 0)


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class ManagerAccountTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school = School.objects.create(name="Manager School", slug="manager-school")
        self.other_school = School.objects.create(name="Other Manager School", slug="other-manager-school")
        self.admin = User.objects.create_user(
            email="admin@manager.test",
            password="DemoPass123!",
            active_school=self.school,
        )
        UserRole.objects.create(
            user=self.admin,
            school=self.school,
            role=RoleChoices.SCHOOL_ADMIN,
        )
        self.client.force_authenticate(user=self.admin)

    def test_school_admin_can_create_and_update_manager_account(self):
        created = self.client.post(
            "/api/v1/accounts/managers/",
            {
                "first_name": "Ayesha",
                "last_name": "Khan",
                "email": "ayesha.manager@example.com",
                "password": "DemoPass123!",
            },
            format="json",
        )

        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.data["role"], RoleChoices.MANAGER)
        self.assertEqual(created.data["full_name"], "Ayesha Khan")
        self.assertEqual(created.data["email"], "ayesha.manager@example.com")
        membership = UserRole.objects.get(pk=created.data["id"])
        self.assertEqual(membership.school, self.school)
        self.assertEqual(membership.user.active_school, self.school)
        self.assertTrue(membership.user.check_password("DemoPass123!"))

        updated = self.client.patch(
            f"/api/v1/accounts/managers/{membership.id}/",
            {
                "first_name": "Aisha",
                "last_name": "Ahmed",
                "is_active": False,
            },
            format="json",
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.data["full_name"], "Aisha Ahmed")
        self.assertFalse(updated.data["is_active"])

    def test_manager_list_is_scoped_to_active_school(self):
        local_user = User.objects.create_user(
            email="local.manager@example.com",
            password="DemoPass123!",
            active_school=self.school,
        )
        local_role = UserRole.objects.create(
            user=local_user,
            school=self.school,
            role=RoleChoices.MANAGER,
        )
        other_user = User.objects.create_user(
            email="other.manager@example.com",
            password="DemoPass123!",
            active_school=self.other_school,
        )
        UserRole.objects.create(
            user=other_user,
            school=self.other_school,
            role=RoleChoices.MANAGER,
        )

        response = self.client.get("/api/v1/accounts/managers/")

        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in response.data["results"]}
        self.assertEqual(ids, {local_role.id})

    def test_deleting_standalone_manager_removes_login_account(self):
        created = self.client.post(
            "/api/v1/accounts/managers/",
            {
                "first_name": "Delete",
                "last_name": "Manager",
                "email": "delete.manager@example.com",
                "password": "DemoPass123!",
            },
            format="json",
        )
        user_id = created.data["user"]

        deleted = self.client.delete(
            f"/api/v1/accounts/managers/{created.data['id']}/"
        )

        self.assertEqual(deleted.status_code, 204)
        self.assertFalse(User.objects.filter(pk=user_id).exists())


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class ManagerProfileImageTests(TestCase):
    def setUp(self):
        self._media_dir = tempfile.mkdtemp(prefix="manager-media-")
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
        self.school = School.objects.create(name="Manager Image School", slug="manager-image-school")
        self.admin = User.objects.create_user(
            email="admin@manager-image.test",
            password="DemoPass123!",
            active_school=self.school,
        )
        UserRole.objects.create(user=self.admin, school=self.school, role=RoleChoices.SCHOOL_ADMIN)
        self.client.force_authenticate(user=self.admin)

    def tearDown(self):
        self._storage_override.disable()
        shutil.rmtree(self._media_dir, ignore_errors=True)
        super().tearDown()

    def _image_file(self, name: str = "manager.png", image_format: str = "PNG"):
        buffer = BytesIO()
        Image.new("RGB", (96, 96), color=(40, 160, 90)).save(buffer, format=image_format)
        return SimpleUploadedFile(name, buffer.getvalue(), content_type=f"image/{image_format.lower()}")

    def test_school_admin_can_create_manager_with_profile_image(self):
        response = self.client.post(
            "/api/v1/accounts/managers/",
            {
                "first_name": "Ayesha",
                "last_name": "Khan",
                "email": "ayesha.image@example.com",
                "password": "DemoPass123!",
                "profile_image": self._image_file(),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)
        membership = UserRole.objects.get(pk=response.data["id"])
        self.assertTrue(membership.user.profile_image.name.startswith("profile-images/users/school-"))
        self.assertTrue(membership.user.profile_image.name.endswith(".webp"))
        self.assertIn(".webp", response.data["profile_image"])

    def test_replacing_and_clearing_manager_profile_image(self):
        created = self.client.post(
            "/api/v1/accounts/managers/",
            {
                "first_name": "Replace",
                "last_name": "Manager",
                "email": "replace.manager.image@example.com",
                "password": "DemoPass123!",
                "profile_image": self._image_file("first.png"),
            },
            format="multipart",
        )
        self.assertEqual(created.status_code, 201)
        manager_id = created.data["id"]
        membership = UserRole.objects.get(pk=manager_id)
        old_name = membership.user.profile_image.name
        storage = membership.user.profile_image.storage

        with self.captureOnCommitCallbacks(execute=True):
            replaced = self.client.patch(
                f"/api/v1/accounts/managers/{manager_id}/",
                {"profile_image": self._image_file("second.png")},
                format="multipart",
            )
        self.assertEqual(replaced.status_code, 200)
        membership.user.refresh_from_db()
        self.assertNotEqual(membership.user.profile_image.name, old_name)
        self.assertFalse(storage.exists(old_name))
        second_name = membership.user.profile_image.name

        with self.captureOnCommitCallbacks(execute=True):
            cleared = self.client.patch(
                f"/api/v1/accounts/managers/{manager_id}/",
                {"profile_image_clear": True},
                format="multipart",
            )
        self.assertEqual(cleared.status_code, 200)
        membership.user.refresh_from_db()
        self.assertEqual(membership.user.profile_image.name, "")
        self.assertFalse(storage.exists(second_name))


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class TeacherProfileImageTests(TestCase):
    def setUp(self):
        self._media_dir = tempfile.mkdtemp(prefix="teacher-media-")
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
        self.school = School.objects.create(name="Teacher Image School", slug="teacher-image-school")
        self.admin = User.objects.create_user(
            email="admin@teacher-image.test",
            password="DemoPass123!",
            active_school=self.school,
        )
        self.manager = User.objects.create_user(
            email="manager@teacher-image.test",
            password="DemoPass123!",
            active_school=self.school,
        )
        UserRole.objects.create(user=self.admin, school=self.school, role=RoleChoices.SCHOOL_ADMIN)
        UserRole.objects.create(user=self.manager, school=self.school, role=RoleChoices.MANAGER)
        self.client.force_authenticate(user=self.admin)

    def tearDown(self):
        self._storage_override.disable()
        shutil.rmtree(self._media_dir, ignore_errors=True)
        super().tearDown()

    def _image_file(self, name: str = "teacher.png", image_format: str = "PNG"):
        buffer = BytesIO()
        Image.new("RGB", (96, 96), color=(220, 80, 40)).save(buffer, format=image_format)
        return SimpleUploadedFile(name, buffer.getvalue(), content_type=f"image/{image_format.lower()}")

    def test_school_admin_can_create_teacher_with_profile_image(self):
        response = self.client.post(
            "/api/v1/accounts/teachers/",
            {
                "first_name": "Sara",
                "email": "sara.image@example.com",
                "password": "DemoPass123!",
                "profile_image": self._image_file(),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)
        profile = TeacherProfile.objects.get(pk=response.data["id"])
        self.assertTrue(profile.profile_image.name.startswith("profile-images/teachers/school-"))
        self.assertTrue(profile.profile_image.name.endswith(".webp"))
        self.assertIn(".webp", response.data["profile_image"])

    def test_invalid_teacher_profile_image_is_rejected(self):
        response = self.client.post(
            "/api/v1/accounts/teachers/",
            {
                "first_name": "Bad",
                "email": "bad.image@example.com",
                "password": "DemoPass123!",
                "profile_image": SimpleUploadedFile("bad.txt", b"not image", content_type="text/plain"),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("profile_image", response.data)

    def test_replacing_and_clearing_teacher_profile_image(self):
        created = self.client.post(
            "/api/v1/accounts/teachers/",
            {
                "first_name": "Replace",
                "email": "replace.image@example.com",
                "password": "DemoPass123!",
                "profile_image": self._image_file("first.png"),
            },
            format="multipart",
        )
        self.assertEqual(created.status_code, 201)
        teacher_id = created.data["id"]
        profile = TeacherProfile.objects.get(pk=teacher_id)
        old_name = profile.profile_image.name
        storage = profile.profile_image.storage

        with self.captureOnCommitCallbacks(execute=True):
            replaced = self.client.patch(
                f"/api/v1/accounts/teachers/{teacher_id}/",
                {"profile_image": self._image_file("second.png")},
                format="multipart",
            )
        self.assertEqual(replaced.status_code, 200)
        profile.refresh_from_db()
        self.assertNotEqual(profile.profile_image.name, old_name)
        self.assertFalse(storage.exists(old_name))
        second_name = profile.profile_image.name

        with self.captureOnCommitCallbacks(execute=True):
            cleared = self.client.patch(
                f"/api/v1/accounts/teachers/{teacher_id}/",
                {"profile_image_clear": True},
                format="multipart",
            )
        self.assertEqual(cleared.status_code, 200)
        profile.refresh_from_db()
        self.assertEqual(profile.profile_image.name, "")
        self.assertFalse(storage.exists(second_name))

    def test_manager_cannot_modify_teacher_profile_images(self):
        created = self.client.post(
            "/api/v1/accounts/teachers/",
            {
                "first_name": "Protected",
                "email": "protected.image@example.com",
                "password": "DemoPass123!",
            },
            format="json",
        )
        teacher_id = created.data["id"]
        self.client.force_authenticate(user=self.manager)
        denied = self.client.patch(
            f"/api/v1/accounts/teachers/{teacher_id}/",
            {"profile_image": self._image_file()},
            format="multipart",
        )
        self.assertEqual(denied.status_code, 403)
