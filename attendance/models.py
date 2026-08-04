from django.conf import settings
from django.db import models
from django.db.models import Q


class AttendanceSession(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_SUBMITTED = "submitted"
    STATUS_CHOICES = (
        (STATUS_DRAFT, "Draft"),
        (STATUS_SUBMITTED, "Submitted"),
    )

    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="attendance_sessions")
    academic_year = models.ForeignKey(
        "schools.AcademicYear", on_delete=models.CASCADE, related_name="attendance_sessions"
    )
    timetable_entry = models.ForeignKey(
        "timetable.TimetableEntry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_sessions",
    )
    section = models.ForeignKey("academics.Section", on_delete=models.CASCADE, related_name="attendance_sessions")
    teacher = models.ForeignKey(
        "accounts.TeacherProfile", on_delete=models.CASCADE, related_name="attendance_sessions"
    )
    subject = models.ForeignKey(
        "academics.Subject",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_sessions",
    )
    date = models.DateField()
    day_of_week = models.PositiveSmallIntegerField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    taken_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_sessions_taken",
    )
    taken_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["school", "date"], name="att_sess_school_date_idx"),
            models.Index(fields=["teacher", "date"], name="att_sess_teacher_date_idx"),
            models.Index(fields=["section", "date"], name="att_sess_section_date_idx"),
            models.Index(fields=["school", "academic_year", "date"], name="att_sess_yr_date_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["timetable_entry", "date"],
                condition=Q(timetable_entry__isnull=False),
                name="att_sess_unique_entry_date",
            ),
            models.UniqueConstraint(
                fields=["school", "section", "teacher", "date", "start_time", "end_time"],
                condition=Q(timetable_entry__isnull=True),
                name="att_sess_unique_orphan_slot",
            ),
        ]
        ordering = ["-date", "start_time", "id"]

    def __str__(self) -> str:
        return f"{self.section_id} {self.date} {self.start_time}-{self.end_time}"


class AttendanceRecord(models.Model):
    STATUS_PRESENT = "present"
    STATUS_ABSENT = "absent"
    STATUS_LATE = "late"
    STATUS_LEAVE = "leave"
    STATUS_CHOICES = (
        (STATUS_PRESENT, "Present"),
        (STATUS_ABSENT, "Absent"),
        (STATUS_LATE, "Late"),
        (STATUS_LEAVE, "Leave"),
    )

    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="attendance_records")
    session = models.ForeignKey(AttendanceSession, on_delete=models.CASCADE, related_name="records")
    student = models.ForeignKey("students.Student", on_delete=models.CASCADE, related_name="attendance_records")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PRESENT)
    remarks = models.CharField(max_length=255, blank=True)
    marked_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["student", "session"], name="att_rec_student_session_idx"),
            models.Index(fields=["school", "student", "status"], name="att_rec_school_stu_st_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["session", "student"], name="att_rec_unique_session_student"),
        ]
        ordering = ["student__roll_number", "student__first_name", "id"]

    def __str__(self) -> str:
        return f"{self.student_id} {self.status} @ {self.session_id}"
