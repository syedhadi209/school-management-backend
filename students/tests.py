from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

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
