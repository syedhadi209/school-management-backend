from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import RoleChoices, UserRole
from academics.models import ClassLevel, Section
from admissions.models import Admission, Inquiry
from schools.models import AcademicYear, School
from students.models import ParentStudentLink, Student

User = get_user_model()


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class AdmissionsEnrollmentTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school = School.objects.create(name="Admit School", slug="admit-school")
        self.other_school = School.objects.create(name="Other Admit", slug="other-admit")
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
            name="Class 2",
            order=2,
        )
        self.section = Section.objects.create(
            school=self.school,
            class_level=self.class_level,
            name="A",
            capacity=2,
        )
        self.other_year = AcademicYear.objects.create(
            school=self.other_school,
            name="2026-2027",
            start_date=date(2026, 4, 1),
            end_date=date(2027, 3, 31),
            is_active=True,
        )
        self.other_class = ClassLevel.objects.create(
            school=self.other_school,
            academic_year=self.other_year,
            name="Class 2",
            order=2,
        )
        self.other_section = Section.objects.create(
            school=self.other_school,
            class_level=self.other_class,
            name="A",
        )

        self.admin = self._user("admin@admit.test", RoleChoices.SCHOOL_ADMIN)
        self.manager = self._user("manager@admit.test", RoleChoices.MANAGER)
        self.teacher = self._user("teacher@admit.test", RoleChoices.TEACHER)

    def _user(self, email, role):
        user = User.objects.create_user(email=email, password="DemoPass123!", active_school=self.school)
        UserRole.objects.create(user=user, school=self.school, role=role)
        return user

    def _applied_payload(self, **overrides):
        payload = {
            "full_name": "Ayesha Khan",
            "first_name": "Ayesha",
            "last_name": "Khan",
            "phone": "03001234567",
            "status": "applied",
            "gender": "female",
            "date_of_birth": "2015-05-01",
            "address": "House 1, Street 2, Lahore",
            "father_name": "Imran Khan",
            "mother_name": "Sana Khan",
            "father_cnic": "35202-1234567-1",
            "parent_email": "parent.ayesha@admit.test",
            "parent_phone": "03007654321",
            "interested_class_level": self.class_level.id,
            "preferred_section": self.section.id,
            "source": "walk_in",
        }
        payload.update(overrides)
        return payload

    def test_quick_inquiry_requires_name_and_contact(self):
        self.client.force_authenticate(user=self.admin)
        missing_contact = self.client.post(
            "/api/v1/inquiries/",
            {"full_name": "Prospect Only"},
            format="json",
        )
        self.assertEqual(missing_contact.status_code, 400)

        ok = self.client.post(
            "/api/v1/inquiries/",
            {"full_name": "Prospect Ok", "phone": "03001112233", "status": "new"},
            format="json",
        )
        self.assertEqual(ok.status_code, 201)

    def test_applied_requires_family_details(self):
        self.client.force_authenticate(user=self.manager)
        response = self.client.post(
            "/api/v1/inquiries/",
            {
                "full_name": "Incomplete",
                "phone": "03001112233",
                "status": "applied",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertTrue(
            any(key in response.data for key in ("date_of_birth", "gender", "address", "parent_email", "father_name"))
        )

    def test_cannot_set_admitted_directly(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            "/api/v1/inquiries/",
            self._applied_payload(status="admitted"),
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("status", response.data)

    def test_rejected_requires_reason(self):
        self.client.force_authenticate(user=self.admin)
        created = self.client.post(
            "/api/v1/inquiries/",
            {"full_name": "Reject Me", "phone": "0300", "status": "new"},
            format="json",
        )
        self.assertEqual(created.status_code, 201)
        response = self.client.patch(
            f"/api/v1/inquiries/{created.data['id']}/",
            {"status": "rejected"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("rejection_reason", response.data)

    def test_admit_and_enrol_copies_family_and_provisions_parent(self):
        self.client.force_authenticate(user=self.admin)
        created = self.client.post("/api/v1/inquiries/", self._applied_payload(), format="json")
        self.assertEqual(created.status_code, 201)
        inquiry_id = created.data["id"]

        response = self.client.post(
            f"/api/v1/inquiries/{inquiry_id}/admit/",
            {"section": self.section.id, "admission_date": "2026-07-01"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["created"])
        student = response.data["student"]
        self.assertEqual(student["father_name"], "Imran Khan")
        self.assertEqual(student["parent_email"], "parent.ayesha@admit.test")
        self.assertEqual(student["father_cnic"], "3520212345671")
        self.assertTrue(student["roll_number"].startswith("STU-"))

        inquiry = Inquiry.objects.get(pk=inquiry_id)
        self.assertEqual(inquiry.status, "admitted")
        admission = Admission.objects.get(inquiry=inquiry)
        self.assertEqual(admission.decision, "approved")
        self.assertEqual(admission.admitted_by_id, self.admin.id)
        self.assertEqual(admission.student_id, student["id"])

        self.assertTrue(
            ParentStudentLink.objects.filter(
                student_id=student["id"],
                parent__user__email="parent.ayesha@admit.test",
            ).exists()
        )
        parent_user = User.objects.get(email="parent.ayesha@admit.test")
        self.assertFalse(parent_user.has_usable_password())

    def test_admit_is_idempotent(self):
        self.client.force_authenticate(user=self.manager)
        created = self.client.post("/api/v1/inquiries/", self._applied_payload(), format="json")
        inquiry_id = created.data["id"]
        first = self.client.post(
            f"/api/v1/inquiries/{inquiry_id}/admit/",
            {"section": self.section.id},
            format="json",
        )
        second = self.client.post(
            f"/api/v1/inquiries/{inquiry_id}/admit/",
            {"section": self.section.id},
            format="json",
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertFalse(second.data["created"])
        self.assertEqual(first.data["student"]["id"], second.data["student"]["id"])
        self.assertEqual(Student.objects.filter(parent_email="parent.ayesha@admit.test").count(), 1)

    def test_section_capacity_enforced(self):
        self.client.force_authenticate(user=self.admin)
        Student.objects.create(
            school=self.school,
            section=self.section,
            first_name="Fill",
            last_name="One",
            status="active",
        )
        Student.objects.create(
            school=self.school,
            section=self.section,
            first_name="Fill",
            last_name="Two",
            status="active",
        )
        created = self.client.post(
            "/api/v1/inquiries/",
            self._applied_payload(parent_email="capacity@admit.test"),
            format="json",
        )
        response = self.client.post(
            f"/api/v1/inquiries/{created.data['id']}/admit/",
            {"section": self.section.id},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("section", response.data)

    def test_cross_school_section_rejected(self):
        self.client.force_authenticate(user=self.admin)
        created = self.client.post(
            "/api/v1/inquiries/",
            self._applied_payload(parent_email="cross@admit.test"),
            format="json",
        )
        response = self.client.post(
            f"/api/v1/inquiries/{created.data['id']}/admit/",
            {"section": self.other_section.id},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_teacher_cannot_access_inquiries(self):
        self.client.force_authenticate(user=self.teacher)
        response = self.client.get("/api/v1/inquiries/")
        self.assertEqual(response.status_code, 403)

    def test_new_inquiry_cannot_be_admitted(self):
        self.client.force_authenticate(user=self.admin)
        created = self.client.post(
            "/api/v1/inquiries/",
            {"full_name": "Too Early", "phone": "0300", "status": "new"},
            format="json",
        )
        response = self.client.post(
            f"/api/v1/inquiries/{created.data['id']}/admit/",
            {"section": self.section.id},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
