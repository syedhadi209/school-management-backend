from django.conf import settings
from django.db import models
from django.db.models import Q


class Exam(models.Model):
    TYPE_CLASS_TEST = "class_test"
    TYPE_MIDTERM = "midterm"
    TYPE_FINAL = "final"
    TYPE_CHOICES = (
        (TYPE_CLASS_TEST, "Class test"),
        (TYPE_MIDTERM, "Midterm"),
        (TYPE_FINAL, "Final"),
    )

    STATUS_DRAFT = "draft"
    STATUS_OPEN = "open"
    STATUS_PUBLISHED = "published"
    STATUS_CHOICES = (
        (STATUS_DRAFT, "Draft"),
        (STATUS_OPEN, "Open"),
        (STATUS_PUBLISHED, "Published"),
    )

    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="exams")
    academic_year = models.ForeignKey("schools.AcademicYear", on_delete=models.CASCADE, related_name="exams")
    name = models.CharField(max_length=100)
    exam_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_MIDTERM)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    section = models.ForeignKey(
        "academics.Section",
        on_delete=models.CASCADE,
        related_name="exams",
        null=True,
        blank=True,
    )
    subject = models.ForeignKey(
        "academics.Subject",
        on_delete=models.CASCADE,
        related_name="exams",
        null=True,
        blank=True,
    )
    max_marks = models.DecimalField(max_digits=6, decimal_places=2, default=100)
    starts_on = models.DateField(null=True, blank=True)
    ends_on = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="exams_created",
    )
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="exams_published",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["school", "academic_year", "name"],
                condition=Q(exam_type__in=["midterm", "final"]),
                name="exam_unique_term_name",
            ),
            models.UniqueConstraint(
                fields=["academic_year", "section", "subject", "name"],
                condition=Q(exam_type="class_test"),
                name="exam_unique_class_test",
            ),
        ]
        ordering = ["-starts_on", "-id"]

    def __str__(self) -> str:
        return f"{self.name} ({self.exam_type})"


class ExamSchedule(models.Model):
    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="exam_schedules")
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="schedules")
    subject = models.ForeignKey("academics.Subject", on_delete=models.CASCADE, related_name="exam_schedules")
    section = models.ForeignKey("academics.Section", on_delete=models.CASCADE, related_name="exam_schedules")
    exam_datetime = models.DateTimeField()


class ExamSheet(models.Model):
    """Uploaded exam paper file (out of scope for mark-entry v1 UI)."""

    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="exam_sheets")
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="file_sheets")
    subject = models.ForeignKey("academics.Subject", on_delete=models.CASCADE, related_name="exam_sheets")
    section = models.ForeignKey("academics.Section", on_delete=models.CASCADE, related_name="exam_sheets")
    uploaded_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True)
    file_url = models.URLField()


class MarkSheet(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_SUBMITTED = "submitted"
    STATUS_CHOICES = (
        (STATUS_DRAFT, "Draft"),
        (STATUS_SUBMITTED, "Submitted"),
    )

    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="mark_sheets")
    academic_year = models.ForeignKey(
        "schools.AcademicYear", on_delete=models.CASCADE, related_name="mark_sheets"
    )
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="mark_sheets")
    section = models.ForeignKey("academics.Section", on_delete=models.CASCADE, related_name="mark_sheets")
    subject = models.ForeignKey("academics.Subject", on_delete=models.CASCADE, related_name="mark_sheets")
    teacher = models.ForeignKey(
        "accounts.TeacherProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mark_sheets",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    max_marks = models.DecimalField(max_digits=6, decimal_places=2, default=100)
    notes = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mark_sheets_submitted",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["exam", "section", "subject"],
                name="mark_sheet_unique_exam_section_subject",
            ),
        ]
        ordering = ["-updated_at", "-id"]

    def __str__(self) -> str:
        return f"{self.exam_id} {self.section_id} {self.subject_id}"


class Mark(models.Model):
    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="marks")
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="marks")
    sheet = models.ForeignKey(
        MarkSheet,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="marks",
    )
    student = models.ForeignKey("students.Student", on_delete=models.CASCADE, related_name="marks")
    subject = models.ForeignKey("academics.Subject", on_delete=models.CASCADE, related_name="marks")
    teacher = models.ForeignKey("accounts.TeacherProfile", on_delete=models.SET_NULL, null=True, blank=True)
    marks_obtained = models.DecimalField(max_digits=6, decimal_places=2)
    max_marks = models.DecimalField(max_digits=6, decimal_places=2, default=100)
    remarks = models.CharField(max_length=255, blank=True)
    marked_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("exam", "student", "subject")
        ordering = ["student__roll_number", "id"]
