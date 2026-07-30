from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

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
