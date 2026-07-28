from django.db import models


class Student(models.Model):
    STATUS_CHOICES = (
        ("active", "Active"),
        ("repeating", "Repeating"),
        ("passed_out", "Passed Out"),
        ("withdrawn", "Withdrawn"),
        ("transferred", "Transferred"),
    )
    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="students")
    section = models.ForeignKey("academics.Section", on_delete=models.SET_NULL, null=True, blank=True, related_name="students")
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True)
    admission_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


class ParentStudentLink(models.Model):
    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="parent_links")
    parent = models.ForeignKey("accounts.ParentProfile", on_delete=models.CASCADE, related_name="children_links")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="parent_links")
    relation = models.CharField(max_length=50, blank=True)

    class Meta:
        unique_together = ("parent", "student")
