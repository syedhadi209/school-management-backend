from datetime import date, time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from academics.models import ClassLevel, Section, Subject, TeacherSubjectAssignment
from accounts.models import ParentProfile, RoleChoices, TeacherProfile, UserRole
from schools.models import AcademicYear, School
from students.models import ParentStudentLink, Student

from .models import Exam, Mark, MarkSheet

User = get_user_model()


class ExamsModuleTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school = School.objects.create(name="Exam School", slug="exam-school")
        self.year = AcademicYear.objects.create(
            school=self.school,
            name="2026-2027",
            start_date=date(2026, 4, 1),
            end_date=date(2027, 3, 31),
            is_active=True,
        )
        self.admin = self._user("admin@ex.test", RoleChoices.SCHOOL_ADMIN)
        self.teacher_user = self._user("ali@ex.test", RoleChoices.TEACHER, first_name="Ali")
        self.teacher2_user = self._user("fatima@ex.test", RoleChoices.TEACHER, first_name="Fatima")
        self.parent_user = self._user("parent@ex.test", RoleChoices.PARENT)
        self.ali = TeacherProfile.objects.create(user=self.teacher_user, school=self.school)
        self.fatima = TeacherProfile.objects.create(user=self.teacher2_user, school=self.school)
        self.parent = ParentProfile.objects.create(user=self.parent_user, school=self.school)

        self.level = ClassLevel.objects.create(
            school=self.school, academic_year=self.year, name="Class 1", order=1
        )
        self.section_a = Section.objects.create(school=self.school, class_level=self.level, name="A")
        self.section_b = Section.objects.create(school=self.school, class_level=self.level, name="B")
        self.section_a.teachers.set([self.ali, self.fatima])
        self.section_b.teachers.set([self.fatima])

        self.math = Subject.objects.create(school=self.school, name="Mathematics")
        self.english = Subject.objects.create(school=self.school, name="English")

        TeacherSubjectAssignment.objects.create(
            school=self.school,
            teacher=self.ali,
            subject=self.math,
            section=self.section_a,
            academic_year=self.year,
        )
        TeacherSubjectAssignment.objects.create(
            school=self.school,
            teacher=self.fatima,
            subject=self.english,
            section=self.section_a,
            academic_year=self.year,
        )

        self.student1 = Student.objects.create(
            school=self.school,
            section=self.section_a,
            first_name="Hadi",
            last_name="Khan",
            status="active",
            roll_number="STU-1",
        )
        self.student2 = Student.objects.create(
            school=self.school,
            section=self.section_a,
            first_name="Sara",
            last_name="Ali",
            status="active",
            roll_number="STU-2",
        )
        ParentStudentLink.objects.create(
            school=self.school, parent=self.parent, student=self.student1, relation="father"
        )

    def _user(self, email, role, first_name="User"):
        user = User.objects.create_user(
            email=email, password="pass12345", first_name=first_name, active_school=self.school
        )
        UserRole.objects.create(user=user, school=self.school, role=role)
        return user

    def test_teacher_creates_class_test_for_assignment(self):
        self.client.force_authenticate(user=self.teacher_user)
        response = self.client.post(
            "/api/v1/exams/",
            {
                "name": "Math Quiz 1",
                "exam_type": "class_test",
                "section": self.section_a.id,
                "subject": self.math.id,
                "max_marks": "50",
                "starts_on": "2026-08-01",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["exam_type"], "class_test")
        self.assertEqual(MarkSheet.objects.filter(exam_id=response.data["id"]).count(), 1)

    def test_teacher_cannot_create_class_test_for_other_section(self):
        self.client.force_authenticate(user=self.teacher_user)
        response = self.client.post(
            "/api/v1/exams/",
            {
                "name": "Math Quiz B",
                "exam_type": "class_test",
                "section": self.section_b.id,
                "subject": self.math.id,
                "max_marks": "50",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_teacher_cannot_create_midterm(self):
        self.client.force_authenticate(user=self.teacher_user)
        response = self.client.post(
            "/api/v1/exams/",
            {"name": "Midterm", "exam_type": "midterm", "max_marks": "100"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_creates_midterm_and_teacher_enters_marks(self):
        self.client.force_authenticate(user=self.admin)
        create = self.client.post(
            "/api/v1/exams/",
            {"name": "Midterm", "exam_type": "midterm", "max_marks": "100", "starts_on": "2026-08-01"},
            format="json",
        )
        self.assertEqual(create.status_code, 201, create.data)
        exam_id = create.data["id"]

        self.client.force_authenticate(user=self.teacher_user)
        enter = self.client.post(
            "/api/v1/mark-sheets/enter/",
            {
                "exam": exam_id,
                "section": self.section_a.id,
                "subject": self.math.id,
                "records": [
                    {"student": self.student1.id, "marks_obtained": "80"},
                    {"student": self.student2.id, "marks_obtained": "70"},
                ],
            },
            format="json",
        )
        self.assertEqual(enter.status_code, 200, enter.data)
        self.assertEqual(enter.data["status"], "submitted")
        self.assertEqual(Mark.objects.filter(exam_id=exam_id).count(), 2)

    def test_incomplete_roster_rejected(self):
        self.client.force_authenticate(user=self.teacher_user)
        create = self.client.post(
            "/api/v1/exams/",
            {
                "name": "Quiz Incomplete",
                "exam_type": "class_test",
                "section": self.section_a.id,
                "subject": self.math.id,
                "max_marks": "100",
            },
            format="json",
        )
        exam_id = create.data["id"]
        response = self.client.post(
            "/api/v1/mark-sheets/enter/",
            {
                "exam": exam_id,
                "section": self.section_a.id,
                "subject": self.math.id,
                "records": [{"student": self.student1.id, "marks_obtained": "80"}],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_publish_rules(self):
        self.client.force_authenticate(user=self.teacher_user)
        create = self.client.post(
            "/api/v1/exams/",
            {
                "name": "Publishable Quiz",
                "exam_type": "class_test",
                "section": self.section_a.id,
                "subject": self.math.id,
                "max_marks": "100",
            },
            format="json",
        )
        exam_id = create.data["id"]
        self.client.post(
            "/api/v1/mark-sheets/enter/",
            {
                "exam": exam_id,
                "section": self.section_a.id,
                "subject": self.math.id,
                "records": [
                    {"student": self.student1.id, "marks_obtained": "90"},
                    {"student": self.student2.id, "marks_obtained": "85"},
                ],
            },
            format="json",
        )
        publish = self.client.post(f"/api/v1/exams/{exam_id}/publish/")
        self.assertEqual(publish.status_code, 200, publish.data)
        self.assertEqual(publish.data["status"], "published")

        self.client.force_authenticate(user=self.admin)
        midterm = self.client.post(
            "/api/v1/exams/",
            {"name": "Final", "exam_type": "final", "max_marks": "100"},
            format="json",
        )
        midterm_id = midterm.data["id"]
        self.client.force_authenticate(user=self.teacher_user)
        forbidden = self.client.post(f"/api/v1/exams/{midterm_id}/publish/")
        self.assertEqual(forbidden.status_code, 403)

        self.client.force_authenticate(user=self.admin)
        # Need marks before publish for term exams
        self.client.force_authenticate(user=self.teacher_user)
        self.client.post(
            "/api/v1/mark-sheets/enter/",
            {
                "exam": midterm_id,
                "section": self.section_a.id,
                "subject": self.math.id,
                "records": [
                    {"student": self.student1.id, "marks_obtained": "75"},
                    {"student": self.student2.id, "marks_obtained": "65"},
                ],
            },
            format="json",
        )
        self.client.force_authenticate(user=self.admin)
        ok = self.client.post(f"/api/v1/exams/{midterm_id}/publish/")
        self.assertEqual(ok.status_code, 200, ok.data)

    def test_parent_sees_only_published_marks(self):
        self.client.force_authenticate(user=self.teacher_user)
        create = self.client.post(
            "/api/v1/exams/",
            {
                "name": "Visible Quiz",
                "exam_type": "class_test",
                "section": self.section_a.id,
                "subject": self.math.id,
                "max_marks": "100",
            },
            format="json",
        )
        exam_id = create.data["id"]
        self.client.post(
            "/api/v1/mark-sheets/enter/",
            {
                "exam": exam_id,
                "section": self.section_a.id,
                "subject": self.math.id,
                "records": [
                    {"student": self.student1.id, "marks_obtained": "88"},
                    {"student": self.student2.id, "marks_obtained": "77"},
                ],
            },
            format="json",
        )

        self.client.force_authenticate(user=self.parent_user)
        before = self.client.get(f"/api/v1/marks/?student={self.student1.id}")
        self.assertEqual(before.status_code, 200)
        self.assertEqual(before.data["count"], 0)

        self.client.force_authenticate(user=self.teacher_user)
        self.client.post(f"/api/v1/exams/{exam_id}/publish/")

        self.client.force_authenticate(user=self.parent_user)
        after = self.client.get(f"/api/v1/marks/?student={self.student1.id}")
        self.assertEqual(after.status_code, 200)
        self.assertEqual(after.data["count"], 1)

    def test_edit_blocked_after_publish(self):
        self.client.force_authenticate(user=self.teacher_user)
        create = self.client.post(
            "/api/v1/exams/",
            {
                "name": "Locked Quiz",
                "exam_type": "class_test",
                "section": self.section_a.id,
                "subject": self.math.id,
                "max_marks": "100",
            },
            format="json",
        )
        exam_id = create.data["id"]
        payload = {
            "exam": exam_id,
            "section": self.section_a.id,
            "subject": self.math.id,
            "records": [
                {"student": self.student1.id, "marks_obtained": "80"},
                {"student": self.student2.id, "marks_obtained": "70"},
            ],
        }
        self.client.post("/api/v1/mark-sheets/enter/", payload, format="json")
        self.client.post(f"/api/v1/exams/{exam_id}/publish/")
        locked = self.client.post("/api/v1/mark-sheets/enter/", payload, format="json")
        self.assertEqual(locked.status_code, 400)
