from django.db import models


class Inquiry(models.Model):
    STATUS_CHOICES = (
        ("new", "New"),
        ("contacted", "Contacted"),
        ("visited", "Visited"),
        ("applied", "Applied"),
        ("admitted", "Admitted"),
        ("rejected", "Rejected"),
    )
    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="inquiries")
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=30, blank=True)
    interested_class = models.CharField(max_length=100, blank=True)
    source = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="new")


class VisitorLog(models.Model):
    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="visitor_logs")
    visitor_name = models.CharField(max_length=255)
    purpose = models.CharField(max_length=255)
    met_with = models.CharField(max_length=255, blank=True)
    check_in = models.DateTimeField(auto_now_add=True)
    check_out = models.DateTimeField(null=True, blank=True)


class Admission(models.Model):
    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="admissions")
    inquiry = models.OneToOneField(Inquiry, on_delete=models.CASCADE, related_name="admission")
    student = models.ForeignKey("students.Student", on_delete=models.SET_NULL, null=True, blank=True)
    decision = models.CharField(max_length=20, default="pending")
