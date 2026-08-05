from decimal import Decimal

from django.db import models


class FeeStructure(models.Model):
    """Monthly tuition amount for a class level (one per school + class)."""

    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="fee_structures")
    class_level = models.ForeignKey(
        "academics.ClassLevel", on_delete=models.CASCADE, related_name="fee_structures"
    )
    name = models.CharField(max_length=100, default="Monthly Tuition")
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["school", "class_level"],
                name="fee_structure_unique_monthly_per_class",
            ),
        ]
        ordering = ["class_level__order", "class_level__name", "id"]

    def __str__(self) -> str:
        return f"{self.class_level_id}: {self.name} ({self.amount})"


class StudentMonthlyFee(models.Model):
    """Per-student monthly tuition snapshot with optional discount."""

    school = models.ForeignKey(
        "schools.School", on_delete=models.CASCADE, related_name="student_monthly_fees"
    )
    student = models.OneToOneField(
        "students.Student", on_delete=models.CASCADE, related_name="monthly_fee"
    )
    fee_structure = models.ForeignKey(
        FeeStructure,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="student_monthly_fees",
    )
    base_amount = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    notes = models.CharField(max_length=255, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-updated_at", "-id"]

    def __str__(self) -> str:
        return f"Student {self.student_id} fee {self.effective_amount}"

    @property
    def effective_amount(self) -> Decimal:
        return max(self.base_amount - self.discount_amount, Decimal("0"))


class Invoice(models.Model):
    TYPE_MONTHLY_FEE = "monthly_fee"
    TYPE_FUND = "fund"
    TYPE_CHOICES = (
        (TYPE_MONTHLY_FEE, "Monthly fee"),
        (TYPE_FUND, "Fund"),
    )

    STATUS_CHOICES = (("unpaid", "Unpaid"), ("partial", "Partial"), ("paid", "Paid"))
    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="invoices")
    student = models.ForeignKey("students.Student", on_delete=models.CASCADE, related_name="invoices")
    fee_structure = models.ForeignKey(FeeStructure, on_delete=models.SET_NULL, null=True, blank=True)
    invoice_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_MONTHLY_FEE)
    fund = models.ForeignKey(
        "funds.Fund",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices",
    )
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="unpaid")
    due_date = models.DateField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["fund", "student"],
                condition=models.Q(invoice_type="fund", fund__isnull=False),
                name="invoice_unique_fund_per_student",
            ),
        ]
        indexes = [
            models.Index(fields=["invoice_type", "status"]),
            models.Index(fields=["fund", "status"]),
        ]

    @property
    def balance(self):
        return max(self.total_amount - self.paid_amount, 0)


class Payment(models.Model):
    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="payments")
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=30, blank=True)
    paid_on = models.DateTimeField(auto_now_add=True)
