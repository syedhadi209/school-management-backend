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
