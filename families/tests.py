from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import RoleChoices, UserRole
from academics.models import ClassLevel, Section
from families.models import Family
from schools.models import AcademicYear, School
from students.models import Student

User = get_user_model()


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class FamilyApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school = School.objects.create(name="Family API School", slug="family-api-school")
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
        self.section = Section.objects.create(school=self.school, class_level=self.class_level, name="A")
        self.admin = User.objects.create_user(
            email="admin@family-api.test",
            password="DemoPass123!",
            active_school=self.school,
        )
        UserRole.objects.create(user=self.admin, school=self.school, role=RoleChoices.SCHOOL_ADMIN)
        self.client.force_authenticate(user=self.admin)

    def test_lookup_family_by_code_returns_members(self):
        family = Family.objects.create(
            school=self.school,
            family_code="FAM-1111",
            primary_contact_email="parent@family-api.test",
        )
        student = Student.objects.create(
            school=self.school,
            section=self.section,
            first_name="Ali",
            last_name="Khan",
            family=family,
            status="active",
        )

        response = self.client.get("/api/v1/families/by-code/?code=fam-1111")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["family_code"], "FAM-1111")
        self.assertEqual(response.data["member_count"], 1)
        self.assertEqual(response.data["members"][0]["id"], student.id)
