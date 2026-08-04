from django.db import models
from django.db.models import Q, F


class TimetableEntry(models.Model):
    DAY_MONDAY = 0
    DAY_TUESDAY = 1
    DAY_WEDNESDAY = 2
    DAY_THURSDAY = 3
    DAY_FRIDAY = 4
    DAY_SATURDAY = 5
    DAY_SUNDAY = 6
    DAY_CHOICES = (
        (DAY_MONDAY, "Monday"),
        (DAY_TUESDAY, "Tuesday"),
        (DAY_WEDNESDAY, "Wednesday"),
        (DAY_THURSDAY, "Thursday"),
        (DAY_FRIDAY, "Friday"),
        (DAY_SATURDAY, "Saturday"),
        (DAY_SUNDAY, "Sunday"),
    )

    SLOT_LECTURE = "lecture"
    SLOT_BREAK = "break"
    SLOT_TYPE_CHOICES = (
        (SLOT_LECTURE, "Lecture"),
        (SLOT_BREAK, "Break"),
    )

    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="timetable_entries")
    academic_year = models.ForeignKey(
        "schools.AcademicYear", on_delete=models.CASCADE, related_name="timetable_entries"
    )
    section = models.ForeignKey("academics.Section", on_delete=models.CASCADE, related_name="timetable_entries")
    slot_type = models.CharField(max_length=20, choices=SLOT_TYPE_CHOICES, default=SLOT_LECTURE)
    subject = models.ForeignKey(
        "academics.Subject",
        on_delete=models.CASCADE,
        related_name="timetable_entries",
        null=True,
        blank=True,
    )
    teacher = models.ForeignKey(
        "accounts.TeacherProfile",
        on_delete=models.CASCADE,
        related_name="timetable_entries",
        null=True,
        blank=True,
    )
    label = models.CharField(max_length=60, blank=True)
    day_of_week = models.PositiveSmallIntegerField(choices=DAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["school", "academic_year", "day_of_week", "start_time"],
                name="tt_school_year_day_start_idx",
            ),
            models.Index(
                fields=["teacher", "day_of_week", "start_time"],
                name="tt_teacher_day_start_idx",
            ),
            models.Index(
                fields=["section", "day_of_week", "start_time"],
                name="tt_section_day_start_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(start_time__lt=F("end_time")),
                name="tt_start_before_end",
            ),
        ]
        ordering = ["day_of_week", "start_time", "id"]

    def __str__(self) -> str:
        day = dict(self.DAY_CHOICES).get(self.day_of_week, self.day_of_week)
        if self.slot_type == self.SLOT_BREAK:
            return f"{self.label or 'Break'} {day} {self.start_time}-{self.end_time}"
        subject = self.subject.name if self.subject_id else "Lecture"
        return f"{subject} {day} {self.start_time}-{self.end_time}"
