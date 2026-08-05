from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from academics.models import ClassLevel, Section
from accounts.models import ParentProfile, RoleChoices, UserRole
from fees.models import Invoice
from funds.models import Fund
from schools.models import AcademicYear, School
from students.models import ParentStudentLink, Student

User = get_user_model()


class FundsModuleTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school = School.objects.create(name="Fund School", slug="fund-school")
        self.year = AcademicYear.objects.create(
            school=self.school,
            name="2026-2027",
            start_date=date(2026, 4, 1),
            end_date=date(2027, 3, 31),
            is_active=True,
        )
        self.admin = self._user("admin@fund.test", RoleChoices.SCHOOL_ADMIN)
        self.manager = self._user("manager@fund.test", RoleChoices.MANAGER)
        self.parent_user = self._user("parent@fund.test", RoleChoices.PARENT)
        self.parent = ParentProfile.objects.create(user=self.parent_user, school=self.school)

        self.level1 = ClassLevel.objects.create(
            school=self.school, academic_year=self.year, name="Class 1", order=1
        )
        self.level2 = ClassLevel.objects.create(
            school=self.school, academic_year=self.year, name="Class 2", order=2
        )
        self.section_a = Section.objects.create(school=self.school, class_level=self.level1, name="A")
        self.section_b = Section.objects.create(school=self.school, class_level=self.level1, name="B")
        self.section_c = Section.objects.create(school=self.school, class_level=self.level2, name="A")

        self.student_a = Student.objects.create(
            school=self.school,
            section=self.section_a,
            first_name="Ali",
            last_name="A",
            status="active",
            roll_number="F-1",
        )
        self.student_b = Student.objects.create(
            school=self.school,
            section=self.section_b,
            first_name="Bina",
            last_name="B",
            status="active",
            roll_number="F-2",
        )
        self.student_c = Student.objects.create(
            school=self.school,
            section=self.section_c,
            first_name="Cara",
            last_name="C",
            status="active",
            roll_number="F-3",
        )
        ParentStudentLink.objects.create(
            school=self.school, parent=self.parent, student=self.student_a, relation="father"
        )

    def _user(self, email, role):
        user = User.objects.create_user(
            email=email, password="pass12345", active_school=self.school
        )
        UserRole.objects.create(user=user, school=self.school, role=role)
        return user

    def test_manager_creates_and_activates_fund(self):
        self.client.force_authenticate(self.manager)
        create = self.client.post(
            "/api/v1/funds/",
            {
                "name": "Annual Fund",
                "amount": "2500",
                "tenure": "annually",
                "class_levels": [self.level1.id],
                "due_on": "2026-12-31",
                "notes": "School development",
            },
            format="json",
        )
        self.assertEqual(create.status_code, 201, create.data)
        fund_id = create.data["id"]
        self.assertEqual(create.data["status"], "draft")

        activate = self.client.post(f"/api/v1/funds/{fund_id}/activate/")
        self.assertEqual(activate.status_code, 200, activate.data)
        self.assertEqual(activate.data["status"], "active")
        self.assertEqual(activate.data["sync"]["created"], 2)

        invoices = Invoice.objects.filter(fund_id=fund_id, invoice_type=Invoice.TYPE_FUND)
        self.assertEqual(invoices.count(), 2)
        self.assertTrue(invoices.filter(student=self.student_a).exists())
        self.assertTrue(invoices.filter(student=self.student_b).exists())
        self.assertFalse(invoices.filter(student=self.student_c).exists())

    def test_payment_updates_fund_invoice_status(self):
        fund = Fund.objects.create(
            school=self.school,
            academic_year=self.year,
            name="Sports Fund",
            amount=Decimal("1000"),
            tenure=Fund.TENURE_ANNUALLY,
            status=Fund.STATUS_ACTIVE,
            due_on=date(2026, 12, 1),
            created_by=self.admin,
        )
        fund.class_levels.add(self.level1)
        invoice = Invoice.objects.create(
            school=self.school,
            student=self.student_a,
            invoice_type=Invoice.TYPE_FUND,
            fund=fund,
            total_amount=Decimal("1000"),
            paid_amount=Decimal("0"),
            status="unpaid",
            due_date=fund.due_on,
        )

        self.client.force_authenticate(self.manager)
        pay = self.client.post(
            "/api/v1/payments/",
            {"invoice": invoice.id, "amount": "400", "method": "cash"},
            format="json",
        )
        self.assertEqual(pay.status_code, 201, pay.data)
        invoice.refresh_from_db()
        self.assertEqual(invoice.paid_amount, Decimal("400"))
        self.assertEqual(invoice.status, "partial")

        overpay = self.client.post(
            "/api/v1/payments/",
            {"invoice": invoice.id, "amount": "700", "method": "cash"},
            format="json",
        )
        self.assertEqual(overpay.status_code, 400)

        settle = self.client.post(
            "/api/v1/payments/",
            {"invoice": invoice.id, "amount": "600", "method": "cash"},
            format="json",
        )
        self.assertEqual(settle.status_code, 201, settle.data)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, "paid")
        self.assertEqual(invoice.paid_amount, Decimal("1000"))

    def test_filter_invoices_by_type(self):
        fund = Fund.objects.create(
            school=self.school,
            academic_year=self.year,
            name="Library Fund",
            amount=Decimal("500"),
            status=Fund.STATUS_ACTIVE,
            created_by=self.admin,
        )
        Invoice.objects.create(
            school=self.school,
            student=self.student_a,
            invoice_type=Invoice.TYPE_FUND,
            fund=fund,
            total_amount=Decimal("500"),
            status="unpaid",
        )
        Invoice.objects.create(
            school=self.school,
            student=self.student_a,
            invoice_type=Invoice.TYPE_MONTHLY_FEE,
            total_amount=Decimal("3000"),
            status="unpaid",
        )

        self.client.force_authenticate(self.admin)
        response = self.client.get("/api/v1/invoices/?invoice_type=fund")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["invoice_type"], "fund")
        self.assertEqual(response.data["results"][0]["fund_name"], "Library Fund")

    def test_parent_sees_typed_invoices(self):
        fund = Fund.objects.create(
            school=self.school,
            academic_year=self.year,
            name="Parent Visible Fund",
            amount=Decimal("800"),
            status=Fund.STATUS_ACTIVE,
            created_by=self.admin,
        )
        Invoice.objects.create(
            school=self.school,
            student=self.student_a,
            invoice_type=Invoice.TYPE_FUND,
            fund=fund,
            total_amount=Decimal("800"),
            status="unpaid",
        )
        Invoice.objects.create(
            school=self.school,
            student=self.student_c,
            invoice_type=Invoice.TYPE_FUND,
            fund=fund,
            total_amount=Decimal("800"),
            status="unpaid",
        )

        self.client.force_authenticate(self.parent_user)
        response = self.client.get("/api/v1/invoices/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["invoice_type"], "fund")

    def test_student_section_change_gets_fund_invoice(self):
        fund = Fund.objects.create(
            school=self.school,
            academic_year=self.year,
            name="Class2 Fund",
            amount=Decimal("1200"),
            status=Fund.STATUS_ACTIVE,
            created_by=self.admin,
        )
        fund.class_levels.add(self.level2)

        self.client.force_authenticate(self.admin)
        response = self.client.post(
            "/api/v1/students/",
            {
                "first_name": "New",
                "last_name": "Kid",
                "section": self.section_c.id,
                "status": "active",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(
            Invoice.objects.filter(
                student_id=response.data["id"],
                fund=fund,
                invoice_type=Invoice.TYPE_FUND,
            ).exists()
        )
