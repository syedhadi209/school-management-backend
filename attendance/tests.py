from datetime import date, time, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from academics.models import ClassLevel, Section, Subject
from accounts.models import ParentProfile, RoleChoices, TeacherProfile, UserRole
from attendance.models import AttendanceRecord, AttendanceSession
from schools.models import AcademicYear, School
from students.models import ParentStudentLink, Student
from timetable.models import TimetableEntry

User = get_user_model()


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class AttendanceAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school = School.objects.create(name="Attendance School", slug="attendance-school", timezone="Asia/Karachi")
        self.other_school = School.objects.create(name="Other School", slug="other-att-school")
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

        self.admin = self._user("admin@att.test", RoleChoices.SCHOOL_ADMIN, self.school)
        self.ali_user = self._user("ali@att.test", RoleChoices.TEACHER, self.school, first_name="Ali")
        self.fatima_user = self._user("fatima@att.test", RoleChoices.TEACHER, self.school, first_name="Fatima")
        self.parent_user = self._user("parent@att.test", RoleChoices.PARENT, self.school)
        self.other_admin = self._user("other@att.test", RoleChoices.SCHOOL_ADMIN, self.other_school)

        self.ali = TeacherProfile.objects.create(user=self.ali_user, school=self.school)
        self.fatima = TeacherProfile.objects.create(user=self.fatima_user, school=self.school)
        self.parent = ParentProfile.objects.create(user=self.parent_user, school=self.school)

        self.class_level = ClassLevel.objects.create(
            school=self.school, academic_year=self.year, name="Class 1", order=1
        )
        self.section = Section.objects.create(school=self.school, class_level=self.class_level, name="A")
        self.section.teachers.set([self.ali, self.fatima])
        self.math = Subject.objects.create(school=self.school, name="Mathematics")
        self.english = Subject.objects.create(school=self.school, name="English")

        self.student1 = Student.objects.create(
            school=self.school, section=self.section, first_name="Hadi", last_name="Khan", status="active"
        )
        self.student2 = Student.objects.create(
            school=self.school, section=self.section, first_name="Sara", last_name="Ali", status="active"
        )
        self.inactive = Student.objects.create(
            school=self.school, section=self.section, first_name="Old", last_name="Student", status="withdrawn"
        )
        ParentStudentLink.objects.create(
            school=self.school, parent=self.parent, student=self.student1, relation="father"
        )

        self.lecture = TimetableEntry.objects.create(
            school=self.school,
            academic_year=self.year,
            section=self.section,
            slot_type=TimetableEntry.SLOT_LECTURE,
            subject=self.math,
            teacher=self.ali,
            day_of_week=0,
            start_time=time(10, 0),
            end_time=time(11, 0),
        )
        self.fatima_lecture = TimetableEntry.objects.create(
            school=self.school,
            academic_year=self.year,
            section=self.section,
            slot_type=TimetableEntry.SLOT_LECTURE,
            subject=self.english,
            teacher=self.fatima,
            day_of_week=0,
            start_time=time(11, 0),
            end_time=time(12, 0),
        )
        self.break_slot = TimetableEntry.objects.create(
            school=self.school,
            academic_year=self.year,
            section=self.section,
            slot_type=TimetableEntry.SLOT_BREAK,
            label="Lunch",
            day_of_week=0,
            start_time=time(12, 0),
            end_time=time(12, 30),
        )

        # Monday 2026-07-27 is a Monday in Karachi
        self.today = date(2026, 7, 27)
        self.fixed_now = timezone.datetime(2026, 7, 27, 5, 15, tzinfo=ZoneInfo("UTC"))  # 10:15 Asia/Karachi

    def _user(self, email, role, school, first_name="User"):
        user = User.objects.create_user(
            email=email, password="DemoPass123!", first_name=first_name, active_school=school
        )
        UserRole.objects.create(user=user, school=school, role=role)
        return user

    def _records_payload(self, statuses=None):
        statuses = statuses or {
            self.student1.id: "present",
            self.student2.id: "absent",
        }
        return [
            {"student": self.student1.id, "status": statuses[self.student1.id], "remarks": ""},
            {"student": self.student2.id, "status": statuses[self.student2.id], "remarks": "Sick"},
        ]

    def test_teacher_takes_attendance(self):
        self.client.force_authenticate(user=self.ali_user)
        with patch("timetable.services.timezone.now", return_value=self.fixed_now):
            response = self.client.post(
                "/api/v1/attendance-sessions/take/",
                {
                    "timetable_entry": self.lecture.id,
                    "date": self.today.isoformat(),
                    "records": self._records_payload(),
                },
                format="json",
            )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["status"], "submitted")
        self.assertEqual(len(response.data["records"]), 2)
        self.assertEqual(AttendanceSession.objects.count(), 1)
        self.assertEqual(AttendanceRecord.objects.count(), 2)

    def test_second_take_upserts(self):
        self.client.force_authenticate(user=self.ali_user)
        payload = {
            "timetable_entry": self.lecture.id,
            "date": self.today.isoformat(),
            "records": self._records_payload(),
        }
        with patch("timetable.services.timezone.now", return_value=self.fixed_now):
            first = self.client.post("/api/v1/attendance-sessions/take/", payload, format="json")
            second = self.client.post(
                "/api/v1/attendance-sessions/take/",
                {
                    **payload,
                    "records": self._records_payload(
                        {self.student1.id: "late", self.student2.id: "present"}
                    ),
                },
                format="json",
            )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201, second.data)
        self.assertEqual(AttendanceSession.objects.count(), 1)
        self.assertEqual(AttendanceRecord.objects.count(), 2)
        self.assertEqual(
            AttendanceRecord.objects.get(student=self.student1).status, "late"
        )

    def test_teacher_cannot_take_other_teachers_lecture(self):
        self.client.force_authenticate(user=self.ali_user)
        with patch("timetable.services.timezone.now", return_value=self.fixed_now):
            response = self.client.post(
                "/api/v1/attendance-sessions/take/",
                {
                    "timetable_entry": self.fatima_lecture.id,
                    "date": self.today.isoformat(),
                    "records": self._records_payload(),
                },
                format="json",
            )
        self.assertEqual(response.status_code, 403)

    def test_teacher_cannot_take_different_day(self):
        self.client.force_authenticate(user=self.ali_user)
        with patch("timetable.services.timezone.now", return_value=self.fixed_now):
            response = self.client.post(
                "/api/v1/attendance-sessions/take/",
                {
                    "timetable_entry": self.lecture.id,
                    "date": (self.today - timedelta(days=1)).isoformat(),
                    "records": self._records_payload(),
                },
                format="json",
            )
        self.assertEqual(response.status_code, 400)

    def test_admin_can_take_past_date(self):
        self.client.force_authenticate(user=self.admin)
        past = self.today - timedelta(days=3)
        response = self.client.post(
            "/api/v1/attendance-sessions/take/",
            {
                "timetable_entry": self.lecture.id,
                "date": past.isoformat(),
                "records": self._records_payload(),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["date"], past.isoformat())

    def test_break_rejected(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            "/api/v1/attendance-sessions/take/",
            {
                "timetable_entry": self.break_slot.id,
                "date": self.today.isoformat(),
                "records": self._records_payload(),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_student_not_in_section_rejected(self):
        outsider = Student.objects.create(
            school=self.school, first_name="Out", last_name="Sider", status="active"
        )
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            "/api/v1/attendance-sessions/take/",
            {
                "timetable_entry": self.lecture.id,
                "date": self.today.isoformat(),
                "records": self._records_payload()
                + [{"student": outsider.id, "status": "present"}],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_parent_sees_only_own_children_records(self):
        session = AttendanceSession.objects.create(
            school=self.school,
            academic_year=self.year,
            timetable_entry=self.lecture,
            section=self.section,
            teacher=self.ali,
            subject=self.math,
            date=self.today,
            day_of_week=0,
            start_time=time(10, 0),
            end_time=time(11, 0),
            status=AttendanceSession.STATUS_SUBMITTED,
            taken_by=self.ali_user,
            taken_at=timezone.now(),
        )
        AttendanceRecord.objects.create(
            school=self.school, session=session, student=self.student1, status="present"
        )
        AttendanceRecord.objects.create(
            school=self.school, session=session, student=self.student2, status="absent"
        )
        self.client.force_authenticate(user=self.parent_user)
        response = self.client.get("/api/v1/attendance-records/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["student"], self.student1.id)

    def test_cross_tenant_isolation(self):
        self.client.force_authenticate(user=self.other_admin)
        response = self.client.post(
            "/api/v1/attendance-sessions/take/",
            {
                "timetable_entry": self.lecture.id,
                "date": self.today.isoformat(),
                "records": self._records_payload(),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_for_entry_draft_and_existing(self):
        self.client.force_authenticate(user=self.ali_user)
        with patch("timetable.services.timezone.now", return_value=self.fixed_now):
            draft = self.client.get(
                f"/api/v1/attendance-sessions/for-entry/?timetable_entry={self.lecture.id}"
            )
            self.assertEqual(draft.status_code, 200, draft.data)
            self.assertIsNone(draft.data["session_id"])
            self.assertEqual(len(draft.data["records"]), 2)

            self.client.post(
                "/api/v1/attendance-sessions/take/",
                {
                    "timetable_entry": self.lecture.id,
                    "date": self.today.isoformat(),
                    "records": self._records_payload(),
                },
                format="json",
            )
            existing = self.client.get(
                f"/api/v1/attendance-sessions/for-entry/?timetable_entry={self.lecture.id}&date={self.today.isoformat()}"
            )
        self.assertEqual(existing.status_code, 200)
        self.assertIsNotNone(existing.data["session_id"])
        self.assertEqual(existing.data["status"], "submitted")

    def test_current_includes_attendance_taken_flag(self):
        self.client.force_authenticate(user=self.ali_user)
        with patch("timetable.services.timezone.now", return_value=self.fixed_now):
            before = self.client.get("/api/v1/timetable-entries/current/")
            self.assertEqual(before.status_code, 200)
            self.assertIsNotNone(before.data["current"])
            self.assertFalse(before.data["current"]["attendance_taken"])

            self.client.post(
                "/api/v1/attendance-sessions/take/",
                {
                    "timetable_entry": self.lecture.id,
                    "date": self.today.isoformat(),
                    "records": self._records_payload(),
                },
                format="json",
            )
            after = self.client.get("/api/v1/timetable-entries/current/")
        self.assertTrue(after.data["current"]["attendance_taken"])
        self.assertIsNotNone(after.data["current"]["attendance_session_id"])

    def test_summary_endpoint(self):
        self.client.force_authenticate(user=self.admin)
        self.client.post(
            "/api/v1/attendance-sessions/take/",
            {
                "timetable_entry": self.lecture.id,
                "date": self.today.isoformat(),
                "records": self._records_payload(),
            },
            format="json",
        )
        response = self.client.get(f"/api/v1/attendance-sessions/summary/?date={self.today.isoformat()}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["sessions_count"], 1)
        self.assertEqual(response.data["present"], 1)
        self.assertEqual(response.data["absent"], 1)
        self.assertEqual(response.data["total_records"], 2)
