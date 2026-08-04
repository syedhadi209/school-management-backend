from datetime import date, time
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from academics.models import ClassLevel, Section, Subject
from accounts.models import ParentProfile, RoleChoices, TeacherProfile, UserRole
from schools.models import AcademicYear, School
from students.models import ParentStudentLink, Student
from timetable.models import TimetableEntry

User = get_user_model()


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class TimetableModuleTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school = School.objects.create(
            name="Timetable School",
            slug="timetable-school",
            timezone="Asia/Karachi",
        )
        self.other_school = School.objects.create(name="Other School", slug="other-school")
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

        self.admin = self._user("admin@tt.test", RoleChoices.SCHOOL_ADMIN, self.school)
        self.manager = self._user("manager@tt.test", RoleChoices.MANAGER, self.school)
        self.teacher_user = self._user("ali@tt.test", RoleChoices.TEACHER, self.school, first_name="Ali")
        self.teacher2_user = self._user("fatima@tt.test", RoleChoices.TEACHER, self.school, first_name="Fatima")
        self.parent_user = self._user("parent@tt.test", RoleChoices.PARENT, self.school)
        self.other_admin = self._user("other@tt.test", RoleChoices.SCHOOL_ADMIN, self.other_school)

        self.ali = TeacherProfile.objects.create(user=self.teacher_user, school=self.school)
        self.fatima = TeacherProfile.objects.create(user=self.teacher2_user, school=self.school)
        self.parent = ParentProfile.objects.create(user=self.parent_user, school=self.school)

        self.class_level = ClassLevel.objects.create(
            school=self.school, academic_year=self.year, name="Class 1", order=1
        )
        self.class_level_b = ClassLevel.objects.create(
            school=self.school, academic_year=self.year, name="Class 2", order=2
        )
        self.section_a = Section.objects.create(
            school=self.school, class_level=self.class_level, name="A"
        )
        self.section_b = Section.objects.create(
            school=self.school, class_level=self.class_level, name="B"
        )
        self.section_c = Section.objects.create(
            school=self.school, class_level=self.class_level_b, name="A"
        )
        self.section_a.teachers.set([self.ali, self.fatima])
        self.section_b.teachers.set([self.ali])
        self.section_c.teachers.set([self.fatima])

        self.math = Subject.objects.create(school=self.school, name="Mathematics")
        self.english = Subject.objects.create(school=self.school, name="English")
        self.other_subject = Subject.objects.create(school=self.other_school, name="History")

        self.student = Student.objects.create(
            school=self.school,
            section=self.section_a,
            first_name="Hadi",
            last_name="Khan",
            status="active",
        )
        ParentStudentLink.objects.create(
            school=self.school, parent=self.parent, student=self.student, relation="father"
        )

        self.other_class = ClassLevel.objects.create(
            school=self.other_school, academic_year=self.other_year, name="Class X", order=1
        )
        self.other_section = Section.objects.create(
            school=self.other_school, class_level=self.other_class, name="A"
        )

    def _user(self, email, role, school, first_name="User"):
        user = User.objects.create_user(
            email=email,
            password="DemoPass123!",
            first_name=first_name,
            active_school=school,
        )
        UserRole.objects.create(user=user, school=school, role=role)
        return user

    def _lecture_payload(self, **overrides):
        payload = {
            "section": self.section_a.id,
            "slot_type": "lecture",
            "subject": self.math.id,
            "teacher": self.ali.id,
            "day_of_week": 0,
            "start_time": "07:00:00",
            "end_time": "08:00:00",
        }
        payload.update(overrides)
        return payload

    def test_create_lecture_success(self):
        self.client.force_authenticate(user=self.manager)
        response = self.client.post("/api/v1/timetable-entries/", self._lecture_payload(), format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["slot_type"], "lecture")
        self.assertEqual(response.data["section_label"], "Class 1-A")
        self.assertEqual(response.data["day_label"], "Monday")
        self.assertEqual(TimetableEntry.objects.count(), 1)

    def test_teacher_double_book_rejected(self):
        self.client.force_authenticate(user=self.admin)
        first = self.client.post("/api/v1/timetable-entries/", self._lecture_payload(), format="json")
        self.assertEqual(first.status_code, 201)
        second = self.client.post(
            "/api/v1/timetable-entries/",
            self._lecture_payload(
                section=self.section_b.id,
                subject=self.english.id,
                start_time="07:30:00",
                end_time="08:30:00",
            ),
            format="json",
        )
        self.assertEqual(second.status_code, 400)
        self.assertIn("Ali", str(second.data))

    def test_section_double_book_rejected(self):
        self.client.force_authenticate(user=self.admin)
        self.client.post("/api/v1/timetable-entries/", self._lecture_payload(), format="json")
        response = self.client.post(
            "/api/v1/timetable-entries/",
            self._lecture_payload(
                subject=self.english.id,
                teacher=self.fatima.id,
                start_time="07:30:00",
                end_time="08:30:00",
            ),
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_adjacent_slots_allowed(self):
        self.client.force_authenticate(user=self.admin)
        first = self.client.post("/api/v1/timetable-entries/", self._lecture_payload(), format="json")
        second = self.client.post(
            "/api/v1/timetable-entries/",
            self._lecture_payload(
                subject=self.english.id,
                teacher=self.fatima.id,
                start_time="08:00:00",
                end_time="09:00:00",
            ),
            format="json",
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201, second.data)

    def test_lecture_overlapping_break_rejected(self):
        self.client.force_authenticate(user=self.admin)
        break_resp = self.client.post(
            "/api/v1/timetable-entries/",
            {
                "section": self.section_a.id,
                "slot_type": "break",
                "label": "Recess",
                "day_of_week": 0,
                "start_time": "10:00:00",
                "end_time": "10:30:00",
            },
            format="json",
        )
        self.assertEqual(break_resp.status_code, 201, break_resp.data)
        lecture = self.client.post(
            "/api/v1/timetable-entries/",
            self._lecture_payload(start_time="10:15:00", end_time="11:00:00"),
            format="json",
        )
        self.assertEqual(lecture.status_code, 400)
        self.assertIn("Recess", str(lecture.data))

    def test_break_requires_label_and_rejects_teacher(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            "/api/v1/timetable-entries/",
            {
                "section": self.section_a.id,
                "slot_type": "break",
                "label": "",
                "teacher": self.ali.id,
                "day_of_week": 1,
                "start_time": "12:00:00",
                "end_time": "12:30:00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("label", response.data)

    def test_teacher_not_on_section_roster_rejected(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            "/api/v1/timetable-entries/",
            self._lecture_payload(section=self.section_c.id, teacher=self.ali.id),
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("teacher", response.data)

    def test_cross_tenant_subject_rejected(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            "/api/v1/timetable-entries/",
            self._lecture_payload(subject=self.other_subject.id),
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_teacher_sees_own_lectures_and_section_breaks(self):
        TimetableEntry.objects.create(
            school=self.school,
            academic_year=self.year,
            section=self.section_a,
            slot_type="lecture",
            subject=self.math,
            teacher=self.ali,
            day_of_week=0,
            start_time=time(7, 0),
            end_time=time(8, 0),
        )
        TimetableEntry.objects.create(
            school=self.school,
            academic_year=self.year,
            section=self.section_a,
            slot_type="break",
            label="Lunch",
            day_of_week=0,
            start_time=time(12, 0),
            end_time=time(12, 30),
        )
        TimetableEntry.objects.create(
            school=self.school,
            academic_year=self.year,
            section=self.section_c,
            slot_type="lecture",
            subject=self.english,
            teacher=self.fatima,
            day_of_week=0,
            start_time=time(9, 0),
            end_time=time(10, 0),
        )

        self.client.force_authenticate(user=self.teacher_user)
        response = self.client.get("/api/v1/timetable-entries/")
        self.assertEqual(response.status_code, 200)
        ids_types = {(item["slot_type"], item.get("label") or item.get("subject_name")) for item in response.data["results"]}
        self.assertIn(("lecture", "Mathematics"), ids_types)
        self.assertIn(("break", "Lunch"), ids_types)
        self.assertNotIn(("lecture", "English"), ids_types)

        write = self.client.post("/api/v1/timetable-entries/", self._lecture_payload(start_time="09:00:00", end_time="10:00:00"), format="json")
        self.assertEqual(write.status_code, 403)

    def test_parent_sees_only_child_section(self):
        TimetableEntry.objects.create(
            school=self.school,
            academic_year=self.year,
            section=self.section_a,
            slot_type="lecture",
            subject=self.math,
            teacher=self.ali,
            day_of_week=0,
            start_time=time(7, 0),
            end_time=time(8, 0),
        )
        TimetableEntry.objects.create(
            school=self.school,
            academic_year=self.year,
            section=self.section_b,
            slot_type="lecture",
            subject=self.math,
            teacher=self.ali,
            day_of_week=0,
            start_time=time(8, 0),
            end_time=time(9, 0),
        )
        self.client.force_authenticate(user=self.parent_user)
        response = self.client.get("/api/v1/timetable-entries/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["section"], self.section_a.id)

        filtered = self.client.get(f"/api/v1/timetable-entries/?student={self.student.id}")
        self.assertEqual(filtered.status_code, 200)
        self.assertEqual(len(filtered.data["results"]), 1)

    def test_current_returns_active_lecture_with_roster(self):
        TimetableEntry.objects.create(
            school=self.school,
            academic_year=self.year,
            section=self.section_a,
            slot_type="lecture",
            subject=self.math,
            teacher=self.ali,
            day_of_week=0,
            start_time=time(10, 0),
            end_time=time(11, 0),
        )
        fixed = timezone.datetime(2026, 7, 27, 5, 15, tzinfo=ZoneInfo("UTC"))  # Mon 10:15 Asia/Karachi
        self.client.force_authenticate(user=self.teacher_user)
        with patch("timetable.services.timezone.now", return_value=fixed):
            response = self.client.get("/api/v1/timetable-entries/current/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIsNotNone(response.data["current"])
        self.assertEqual(response.data["current"]["slot_type"], "lecture")
        self.assertEqual(response.data["current"]["section_label"], "Class 1-A")
        self.assertEqual(len(response.data["current"]["roster"]), 1)
        self.assertEqual(response.data["current"]["roster"][0]["first_name"], "Hadi")

    def test_current_returns_break_when_in_break(self):
        TimetableEntry.objects.create(
            school=self.school,
            academic_year=self.year,
            section=self.section_a,
            slot_type="break",
            label="Lunch",
            day_of_week=0,
            start_time=time(12, 0),
            end_time=time(12, 30),
        )
        fixed = timezone.datetime(2026, 7, 27, 7, 10, tzinfo=ZoneInfo("UTC"))  # Mon 12:10 Asia/Karachi
        self.client.force_authenticate(user=self.teacher_user)
        with patch("timetable.services.timezone.now", return_value=fixed):
            response = self.client.get("/api/v1/timetable-entries/current/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["current"]["slot_type"], "break")
        self.assertEqual(response.data["current"]["label"], "Lunch")

    def test_bulk_break_creates_and_reports_conflicts(self):
        TimetableEntry.objects.create(
            school=self.school,
            academic_year=self.year,
            section=self.section_a,
            slot_type="lecture",
            subject=self.math,
            teacher=self.ali,
            day_of_week=2,
            start_time=time(12, 0),
            end_time=time(12, 30),
        )
        self.client.force_authenticate(user=self.manager)
        response = self.client.post(
            "/api/v1/timetable-entries/bulk-break/",
            {
                "day_of_week": 2,
                "start_time": "12:00:00",
                "end_time": "12:30:00",
                "label": "Lunch",
                "section_ids": [self.section_a.id, self.section_b.id],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["created_count"], 1)
        self.assertEqual(response.data["conflict_count"], 1)
        self.assertEqual(response.data["created"][0]["section"], self.section_b.id)

    def test_bulk_break_by_class_level(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            "/api/v1/timetable-entries/bulk-break/",
            {
                "day_of_week": 3,
                "start_time": "10:00:00",
                "end_time": "10:20:00",
                "label": "Recess",
                "class_level_ids": [self.class_level.id],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["created_count"], 2)
