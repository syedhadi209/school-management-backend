from django.db import models


class Exam(models.Model):
    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="exams")
    academic_year = models.ForeignKey("schools.AcademicYear", on_delete=models.CASCADE, related_name="exams")
    name = models.CharField(max_length=100)
    starts_on = models.DateField(null=True, blank=True)
    ends_on = models.DateField(null=True, blank=True)

    class Meta:
        unique_together = ("school", "academic_year", "name")


class ExamSchedule(models.Model):
    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="exam_schedules")
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="schedules")
    subject = models.ForeignKey("academics.Subject", on_delete=models.CASCADE, related_name="exam_schedules")
    section = models.ForeignKey("academics.Section", on_delete=models.CASCADE, related_name="exam_schedules")
    exam_datetime = models.DateTimeField()


class ExamSheet(models.Model):
    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="exam_sheets")
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="sheets")
    subject = models.ForeignKey("academics.Subject", on_delete=models.CASCADE, related_name="exam_sheets")
    section = models.ForeignKey("academics.Section", on_delete=models.CASCADE, related_name="exam_sheets")
    uploaded_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True)
    file_url = models.URLField()


class Mark(models.Model):
    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="marks")
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="marks")
    student = models.ForeignKey("students.Student", on_delete=models.CASCADE, related_name="marks")
    subject = models.ForeignKey("academics.Subject", on_delete=models.CASCADE, related_name="marks")
    teacher = models.ForeignKey("accounts.TeacherProfile", on_delete=models.SET_NULL, null=True, blank=True)
    marks_obtained = models.DecimalField(max_digits=6, decimal_places=2)
    max_marks = models.DecimalField(max_digits=6, decimal_places=2, default=100)

    class Meta:
        unique_together = ("exam", "student", "subject")
