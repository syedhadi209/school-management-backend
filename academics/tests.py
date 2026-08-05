from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import RoleChoices, UserRole
from academics.models import ClassLevel, Section
from schools.models import AcademicYear, School

User = get_user_model()


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class DefaultSectionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school = School.objects.create(name="Section School", slug="section-school")
        self.year = AcademicYear.objects.create(
            school=self.school,
            name="2026-2027",
            start_date=date(2026, 4, 1),
            end_date=date(2027, 3, 31),
            is_active=True,
        )
        self.admin = User.objects.create_user(
            email="admin@sections.test",
            password="DemoPass123!",
            active_school=self.school,
        )
        UserRole.objects.create(user=self.admin, school=self.school, role=RoleChoices.SCHOOL_ADMIN)

    def test_creating_class_creates_default_section(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            "/api/v1/class-levels/",
            {"name": "Class 3", "order": 3},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        class_level = ClassLevel.objects.get(pk=response.data["id"])
        sections = Section.objects.filter(class_level=class_level)
        self.assertEqual(sections.count(), 1)
        self.assertEqual(sections.first().name, "A")
        self.assertEqual(sections.first().school_id, self.school.id)

    def test_creating_class_with_monthly_fee(self):
        from decimal import Decimal

        from fees.models import FeeStructure

        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            "/api/v1/class-levels/",
            {"name": "Class Fee Test", "order": 40, "monthly_fee_amount": "3000"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Decimal(str(response.data["monthly_fee_amount"])), Decimal("3000.00"))
        class_id = response.data["id"]
        fee = FeeStructure.objects.get(class_level_id=class_id)
        self.assertEqual(fee.amount, Decimal("3000.00"))

        update = self.client.patch(
            f"/api/v1/class-levels/{class_id}/",
            {"monthly_fee_amount": "3500"},
            format="json",
        )
        self.assertEqual(update.status_code, 200, update.data)
        self.assertEqual(Decimal(str(update.data["monthly_fee_amount"])), Decimal("3500.00"))
        fee.refresh_from_db()
        self.assertEqual(fee.amount, Decimal("3500.00"))

    def test_new_class_appears_in_section_lookup(self):
        self.client.force_authenticate(user=self.admin)
        self.client.post("/api/v1/class-levels/", {"name": "Class 4", "order": 4}, format="json")
        response = self.client.get("/api/v1/sections/?page=1&page_size=200")
        self.assertEqual(response.status_code, 200)
        class_names = {section["class_level_name"] for section in response.data["results"]}
        self.assertIn("Class 4", class_names)

    def test_page_size_query_param_supported(self):
        self.client.force_authenticate(user=self.admin)
        for index in range(1, 26):
            self.client.post(
                "/api/v1/class-levels/",
                {"name": f"Level {index}", "order": index},
                format="json",
            )
        default_page = self.client.get("/api/v1/sections/")
        larger_page = self.client.get("/api/v1/sections/?page_size=100")
        self.assertEqual(len(default_page.data["results"]), 20)
        self.assertEqual(len(larger_page.data["results"]), 25)

    def test_backfill_command_adds_missing_sections(self):
        bare = ClassLevel.objects.create(
            school=self.school,
            academic_year=self.year,
            name="Legacy Class",
            order=99,
        )
        self.assertEqual(Section.objects.filter(class_level=bare).count(), 0)

        from django.core.management import call_command

        call_command("backfill_default_sections")
        self.assertEqual(Section.objects.filter(class_level=bare).count(), 1)


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class SectionTeacherAssignmentTests(TestCase):
    def setUp(self):
        from accounts.models import TeacherProfile

        self.client = APIClient()
        self.school = School.objects.create(name="Multi Teacher School", slug="multi-teacher-school")
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
        self.admin = User.objects.create_user(
            email="admin@multi.example.com",
            password="DemoPass123!",
            active_school=self.school,
        )
        UserRole.objects.create(user=self.admin, school=self.school, role=RoleChoices.SCHOOL_ADMIN)

        self.teachers = []
        for index, name in enumerate(["Ali", "Fatima", "Hassan"], start=1):
            user = User.objects.create_user(
                email=f"{name.lower()}@multi.example.com",
                password="DemoPass123!",
                first_name=name,
                active_school=self.school,
            )
            UserRole.objects.create(user=user, school=self.school, role=RoleChoices.TEACHER)
            profile = TeacherProfile.objects.create(user=user, school=self.school)
            self.teachers.append(profile)

        self.client.force_authenticate(user=self.admin)

    def test_section_supports_multiple_teachers_and_optional_incharge(self):
        response = self.client.post(
            "/api/v1/sections/",
            {
                "name": "A",
                "class_level": self.class_level.id,
                "capacity": 30,
                "shift": "daily",
                "teachers": [self.teachers[0].id, self.teachers[1].id],
                "class_teacher": self.teachers[0].id,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(set(response.data["teachers"]), {self.teachers[0].id, self.teachers[1].id})
        self.assertEqual(response.data["class_teacher"], self.teachers[0].id)
        self.assertIn("Ali", response.data["class_teacher_name"])

        without_incharge = self.client.post(
            "/api/v1/sections/",
            {
                "name": "B",
                "class_level": self.class_level.id,
                "capacity": 28,
                "shift": "daily",
                "teachers": [self.teachers[1].id, self.teachers[2].id],
                "class_teacher": None,
            },
            format="json",
        )
        self.assertEqual(without_incharge.status_code, 201)
        self.assertIsNone(without_incharge.data["class_teacher"])
        self.assertEqual(
            set(without_incharge.data["teachers"]),
            {self.teachers[1].id, self.teachers[2].id},
        )

    def test_same_teacher_can_teach_multiple_sections(self):
        first = self.client.post(
            "/api/v1/sections/",
            {
                "name": "A",
                "class_level": self.class_level.id,
                "capacity": 30,
                "shift": "daily",
                "teachers": [self.teachers[0].id],
            },
            format="json",
        )
        second = self.client.post(
            "/api/v1/sections/",
            {
                "name": "B",
                "class_level": self.class_level.id,
                "capacity": 30,
                "shift": "daily",
                "teachers": [self.teachers[0].id, self.teachers[1].id],
            },
            format="json",
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(self.teachers[0].teaching_sections.count(), 2)

    def test_class_incharge_is_auto_added_to_assigned_teachers(self):
        response = self.client.post(
            "/api/v1/sections/",
            {
                "name": "C",
                "class_level": self.class_level.id,
                "capacity": 25,
                "shift": "daily",
                "teachers": [self.teachers[1].id],
                "class_teacher": self.teachers[0].id,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            set(response.data["teachers"]),
            {self.teachers[0].id, self.teachers[1].id},
        )
