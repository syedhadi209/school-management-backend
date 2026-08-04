from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import RoleChoices, UserRole
from admissions.models import Inquiry
from schools.models import AcademicYear, School

User = get_user_model()


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class SchoolDashboardStatsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school_a = School.objects.create(name="School A", slug="school-a")
        self.school_b = School.objects.create(name="School B", slug="school-b")
        AcademicYear.objects.create(
            school=self.school_a,
            name="2026-2027",
            start_date=date(2026, 4, 1),
            end_date=date(2027, 3, 31),
            is_active=True,
        )
        self.admin_a = User.objects.create_user(
            email="admin-a@example.com",
            password="DemoPass123!",
            active_school=self.school_a,
        )
        UserRole.objects.create(user=self.admin_a, school=self.school_a, role=RoleChoices.SCHOOL_ADMIN)

        Inquiry.objects.create(school=self.school_a, full_name="Ali Khan", status="new")
        Inquiry.objects.create(school=self.school_b, full_name="Other School Kid", status="new")

    def test_recent_activity_is_scoped_to_active_school(self):
        self.client.force_authenticate(user=self.admin_a)
        response = self.client.get("/api/v1/analytics/dashboard/")
        self.assertEqual(response.status_code, 200)
        titles = [item["title"] for item in response.data["recent_activity"]]
        self.assertTrue(any("Ali Khan" in title for title in titles))
        self.assertFalse(any("Other School Kid" in title for title in titles))

    def test_empty_school_returns_empty_activity(self):
        empty_school = School.objects.create(name="Empty School", slug="empty-school")
        admin = User.objects.create_user(
            email="empty@example.com",
            password="DemoPass123!",
            active_school=empty_school,
        )
        UserRole.objects.create(user=admin, school=empty_school, role=RoleChoices.SCHOOL_ADMIN)
        self.client.force_authenticate(user=admin)
        response = self.client.get("/api/v1/analytics/dashboard/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["recent_activity"], [])
        self.assertEqual(response.data["stats"]["active_students"], 0)
