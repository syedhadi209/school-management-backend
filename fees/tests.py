from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from rest_framework.test import APIClient

from academics.models import ClassLevel, Section
from accounts.models import RoleChoices, UserRole
from fees.models import FeeStructure, StudentMonthlyFee
from schools.models import AcademicYear, School
from students.models import Student

User = get_user_model()


class StudentMonthlyFeeTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school = School.objects.create(name="Fee School", slug="fee-school")
        self.year = AcademicYear.objects.create(
            school=self.school,
            name="2026-2027",
            start_date=date(2026, 4, 1),
            end_date=date(2027, 3, 31),
            is_active=True,
        )
        self.admin = self._user("admin@fee.test", RoleChoices.SCHOOL_ADMIN)
        self.manager = self._user("manager@fee.test", RoleChoices.MANAGER)
        self.level = ClassLevel.objects.create(
            school=self.school, academic_year=self.year, name="Class 1", order=1
        )
        self.section = Section.objects.create(school=self.school, class_level=self.level, name="A")
        self.fee = FeeStructure.objects.create(
            school=self.school,
            class_level=self.level,
            name="Monthly Tuition",
            amount=Decimal("3000"),
        )

    def _user(self, email, role, **extra):
        user = User.objects.create_user(
            email=email,
            password="pass12345",
            active_school=self.school,
            **extra,
        )
        UserRole.objects.create(user=user, role=role, school=self.school)
        return user

    def test_unique_fee_per_class(self):
        with self.assertRaises(IntegrityError):
            FeeStructure.objects.create(
                school=self.school,
                class_level=self.level,
                name="Duplicate",
                amount=Decimal("4000"),
            )

    def test_api_rejects_duplicate_fee(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            "/api/v1/fee-structures/",
            {"class_level": self.level.id, "name": "Another", "amount": "4000"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("class_level", response.data)

    def test_manager_can_list_fee_structures(self):
        self.client.force_authenticate(self.manager)
        response = self.client.get("/api/v1/fee-structures/")
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.data["count"], 1)

    def test_manager_cannot_create_fee(self):
        other = ClassLevel.objects.create(
            school=self.school, academic_year=self.year, name="Class 2", order=2
        )
        self.client.force_authenticate(self.manager)
        response = self.client.post(
            "/api/v1/fee-structures/",
            {"class_level": other.id, "name": "Monthly Tuition", "amount": "3500"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_student_create_with_discount(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            "/api/v1/students/",
            {
                "first_name": "Hadi",
                "last_name": "Khan",
                "section": self.section.id,
                "status": "active",
                "discount_amount": "500",
                "fee_notes": "Sibling discount",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Decimal(str(response.data["monthly_fee_base"])), Decimal("3000"))
        self.assertEqual(Decimal(str(response.data["monthly_fee_discount"])), Decimal("500"))
        self.assertEqual(Decimal(str(response.data["monthly_fee_effective"])), Decimal("2500"))

        fee = StudentMonthlyFee.objects.get(student_id=response.data["id"])
        self.assertEqual(fee.base_amount, Decimal("3000"))
        self.assertEqual(fee.discount_amount, Decimal("500"))
        self.assertEqual(fee.effective_amount, Decimal("2500"))
        self.assertEqual(fee.notes, "Sibling discount")

    def test_discount_above_base_rejected(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            "/api/v1/students/",
            {
                "first_name": "Too",
                "last_name": "Much",
                "section": self.section.id,
                "status": "active",
                "discount_amount": "5000",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_student_without_section_has_no_fee(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            "/api/v1/students/",
            {
                "first_name": "No",
                "last_name": "Section",
                "status": "pending",
                "discount_amount": "100",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertIsNone(response.data["monthly_fee_base"])
        self.assertFalse(StudentMonthlyFee.objects.filter(student_id=response.data["id"]).exists())

    def test_for_class_endpoint(self):
        self.client.force_authenticate(self.manager)
        response = self.client.get(f"/api/v1/fee-structures/for-class/?class_level={self.level.id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Decimal(str(response.data["amount"])), Decimal("3000"))
