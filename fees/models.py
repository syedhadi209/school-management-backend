from django.db import models


class FeeStructure(models.Model):
    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="fee_structures")
    class_level = models.ForeignKey("academics.ClassLevel", on_delete=models.CASCADE, related_name="fee_structures")
    name = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)


class Invoice(models.Model):
    STATUS_CHOICES = (("unpaid", "Unpaid"), ("partial", "Partial"), ("paid", "Paid"))
    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="invoices")
    student = models.ForeignKey("students.Student", on_delete=models.CASCADE, related_name="invoices")
    fee_structure = models.ForeignKey(FeeStructure, on_delete=models.SET_NULL, null=True, blank=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="unpaid")
    due_date = models.DateField(null=True, blank=True)


class Payment(models.Model):
    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="payments")
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=30, blank=True)
    paid_on = models.DateTimeField(auto_now_add=True)
