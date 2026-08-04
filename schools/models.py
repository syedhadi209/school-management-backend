from django.db import models


class School(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    logo = models.URLField(blank=True)
    address = models.TextField(blank=True)
    timezone = models.CharField(
        max_length=64,
        default="Asia/Karachi",
        help_text="IANA timezone used for timetable and attendance local-time resolution.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name


class AcademicYear(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="academic_years")
    name = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=False)

    class Meta:
        unique_together = ("school", "name")

    def __str__(self) -> str:
        return f"{self.school.name} - {self.name}"


class SchoolSubscription(models.Model):
    STATUS_CHOICES = (
        ("trial", "Trial"),
        ("active", "Active"),
        ("suspended", "Suspended"),
        ("churned", "Churned"),
    )
    school = models.OneToOneField(School, on_delete=models.CASCADE, related_name="subscription")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="trial")
    plan_code = models.CharField(max_length=50, default="basic")
    renews_on = models.DateField(null=True, blank=True)

