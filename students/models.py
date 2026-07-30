from django.db import models, transaction

from core.identifiers import next_readable_id


class Student(models.Model):
    STATUS_CHOICES = (
        ("active", "Active"),
        ("pending", "Pending"),
        ("waiting_list", "Waiting List"),
        ("repeating", "Repeating"),
        ("passed_out", "Passed Out"),
        ("withdrawn", "Withdrawn"),
        ("transferred", "Transferred"),
        ("archived", "Archived"),
    )
    GENDER_CHOICES = (
        ("male", "Male"),
        ("female", "Female"),
        ("other", "Other"),
    )
    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="students")
    section = models.ForeignKey(
        "academics.Section", on_delete=models.SET_NULL, null=True, blank=True, related_name="students"
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True)
    roll_number = models.CharField(max_length=30, blank=True)
    board_roll_number = models.CharField(max_length=50, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    guardian_phone = models.CharField(max_length=30, blank=True)
    parent_alternate_phone = models.CharField(max_length=30, blank=True)
    parent_email = models.EmailField(blank=True)
    parent_occupation = models.CharField(max_length=150, blank=True)
    father_name = models.CharField(max_length=150, blank=True)
    mother_name = models.CharField(max_length=150, blank=True)
    father_cnic = models.CharField(max_length=20, blank=True)
    mother_cnic = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    region = models.CharField(max_length=100, blank=True)
    admission_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["school", "roll_number"],
                name="unique_student_roll_number_per_school",
                condition=~models.Q(roll_number=""),
            ),
            models.UniqueConstraint(
                fields=["school", "board_roll_number"],
                name="unique_student_board_roll_number_per_school",
                condition=~models.Q(board_roll_number=""),
            ),
        ]

    def save(self, *args, **kwargs):
        if self.board_roll_number:
            self.board_roll_number = self.board_roll_number.strip()
        if self.parent_email:
            self.parent_email = self.parent_email.strip().lower()
        if not self.roll_number and self.school_id:
            with transaction.atomic():
                self.roll_number = next_readable_id(
                    Student.objects.select_for_update(),
                    field_name="roll_number",
                    prefix="STU",
                    school_id=self.school_id,
                )
                return super().save(*args, **kwargs)
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


class ParentStudentLink(models.Model):
    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="parent_links")
    parent = models.ForeignKey("accounts.ParentProfile", on_delete=models.CASCADE, related_name="children_links")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="parent_links")
    relation = models.CharField(max_length=50, blank=True)

    class Meta:
        unique_together = ("parent", "student")
