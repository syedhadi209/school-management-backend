from django.conf import settings
from django.db import models


class Fund(models.Model):
    TENURE_MONTHLY = "monthly"
    TENURE_QUARTERLY = "quarterly"
    TENURE_ANNUALLY = "annually"
    TENURE_CHOICES = (
        (TENURE_MONTHLY, "Monthly"),
        (TENURE_QUARTERLY, "Quarterly"),
        (TENURE_ANNUALLY, "Annually"),
    )

    STATUS_DRAFT = "draft"
    STATUS_ACTIVE = "active"
    STATUS_CLOSED = "closed"
    STATUS_CHOICES = (
        (STATUS_DRAFT, "Draft"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_CLOSED, "Closed"),
    )

    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="funds")
    academic_year = models.ForeignKey(
        "schools.AcademicYear", on_delete=models.CASCADE, related_name="funds"
    )
    name = models.CharField(max_length=120)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    tenure = models.CharField(max_length=20, choices=TENURE_CHOICES, default=TENURE_ANNUALLY)
    class_levels = models.ManyToManyField(
        "academics.ClassLevel", related_name="funds", blank=True
    )
    starts_on = models.DateField(null=True, blank=True)
    due_on = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="funds_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["school", "academic_year", "name"],
                name="fund_unique_name_per_year",
            ),
        ]
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"{self.name} ({self.tenure})"
