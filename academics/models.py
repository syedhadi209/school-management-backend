from django.db import models


class ClassLevel(models.Model):
    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="class_levels")
    academic_year = models.ForeignKey("schools.AcademicYear", on_delete=models.CASCADE, related_name="class_levels")
    name = models.CharField(max_length=100)
    order = models.PositiveIntegerField(default=1)
    is_board_class = models.BooleanField(
        default=False,
        help_text="When enabled, students in this class can have a board examination roll number.",
    )

    class Meta:
        unique_together = ("school", "academic_year", "name")
        ordering = ["order", "name"]


class Section(models.Model):
    SHIFT_CHOICES = (
        ("mwf", "MWF"),
        ("tthf", "TTHF"),
        ("daily", "Daily"),
    )
    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="sections")
    class_level = models.ForeignKey(ClassLevel, on_delete=models.CASCADE, related_name="sections")
    name = models.CharField(max_length=50)
    capacity = models.PositiveIntegerField(default=30)
    shift = models.CharField(max_length=10, choices=SHIFT_CHOICES, default="daily")
    class_teacher = models.ForeignKey(
        "accounts.TeacherProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="homeroom_sections",
    )

    class Meta:
        unique_together = ("class_level", "name")


class Subject(models.Model):
    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="subjects")
    name = models.CharField(max_length=100)

    class Meta:
        unique_together = ("school", "name")


class ClassSubject(models.Model):
    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="class_subjects")
    class_level = models.ForeignKey(ClassLevel, on_delete=models.CASCADE, related_name="class_subjects")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="class_subjects")

    class Meta:
        unique_together = ("class_level", "subject")


class TeacherSubjectAssignment(models.Model):
    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="teacher_assignments")
    teacher = models.ForeignKey("accounts.TeacherProfile", on_delete=models.CASCADE, related_name="assignments")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="teacher_assignments")
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name="teacher_assignments")
    academic_year = models.ForeignKey(
        "schools.AcademicYear", on_delete=models.CASCADE, related_name="teacher_assignments"
    )

    class Meta:
        unique_together = ("teacher", "subject", "section", "academic_year")


class PassingCriteria(models.Model):
    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="passing_criteria")
    class_level = models.ForeignKey(ClassLevel, on_delete=models.CASCADE, related_name="passing_criteria")
    academic_year = models.ForeignKey("schools.AcademicYear", on_delete=models.CASCADE, related_name="passing_criteria")
    min_percentage = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        unique_together = ("class_level", "academic_year")
