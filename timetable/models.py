from django.db import models


class TimetableEntry(models.Model):
    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="timetable_entries")
    academic_year = models.ForeignKey("schools.AcademicYear", on_delete=models.CASCADE, related_name="timetable_entries")
    section = models.ForeignKey("academics.Section", on_delete=models.CASCADE, related_name="timetable_entries")
    subject = models.ForeignKey("academics.Subject", on_delete=models.CASCADE, related_name="timetable_entries")
    teacher = models.ForeignKey("accounts.TeacherProfile", on_delete=models.CASCADE, related_name="timetable_entries")
    day_of_week = models.IntegerField()
    period_label = models.CharField(max_length=50)

    class Meta:
        unique_together = (
            ("section", "day_of_week", "period_label"),
            ("teacher", "day_of_week", "period_label"),
        )
