from django.conf import settings
from django.db import models
from django.utils import timezone


def inquiry_profile_image_path(instance: "Inquiry", filename: str) -> str:
    from uuid import uuid4

    school_id = instance.school_id or "unknown"
    return f"profile-images/inquiries/school-{school_id}/{uuid4().hex}.webp"


class Inquiry(models.Model):
    STATUS_CHOICES = (
        ("new", "New"),
        ("contacted", "Contacted"),
        ("visited", "Visited"),
        ("applied", "Applied"),
        ("admitted", "Admitted"),
        ("rejected", "Rejected"),
    )
    GENDER_CHOICES = (
        ("male", "Male"),
        ("female", "Female"),
        ("other", "Other"),
    )

    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="inquiries")
    full_name = models.CharField(max_length=255)
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    # Legacy free-text class; prefer interested_class_level going forward.
    interested_class = models.CharField(max_length=100, blank=True)
    interested_class_level = models.ForeignKey(
        "academics.ClassLevel",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inquiries",
    )
    preferred_section = models.ForeignKey(
        "academics.Section",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="preferred_inquiries",
    )
    source = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="new")
    notes = models.TextField(blank=True)
    follow_up_date = models.DateField(null=True, blank=True)
    application_date = models.DateField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    # Family block (mirrored onto Student at enrolment)
    father_name = models.CharField(max_length=150, blank=True)
    mother_name = models.CharField(max_length=150, blank=True)
    father_cnic = models.CharField(max_length=20, blank=True)
    mother_cnic = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    region = models.CharField(max_length=100, blank=True)
    parent_email = models.EmailField(blank=True)
    parent_phone = models.CharField(max_length=30, blank=True)
    parent_alternate_phone = models.CharField(max_length=30, blank=True)
    parent_occupation = models.CharField(max_length=150, blank=True)
    board_roll_number = models.CharField(max_length=50, blank=True)
    profile_image = models.ImageField(upload_to=inquiry_profile_image_path, blank=True)
    family_lookup_code = models.CharField(max_length=32, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if self.parent_email:
            self.parent_email = self.parent_email.strip().lower()
        if self.email:
            self.email = self.email.strip().lower()
        # Keep full_name in sync when structured names are provided.
        if self.first_name or self.last_name:
            composed = f"{self.first_name} {self.last_name}".strip()
            if composed:
                self.full_name = composed
        elif self.full_name and not self.first_name:
            parts = self.full_name.strip().split(None, 1)
            self.first_name = parts[0]
            self.last_name = parts[1] if len(parts) > 1 else ""
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.full_name


class VisitorLog(models.Model):
    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="visitor_logs")
    visitor_name = models.CharField(max_length=255)
    purpose = models.CharField(max_length=255)
    met_with = models.CharField(max_length=255, blank=True)
    check_in = models.DateTimeField(auto_now_add=True)
    check_out = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return self.visitor_name


class Admission(models.Model):
    DECISION_CHOICES = (
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    )

    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="admissions")
    inquiry = models.OneToOneField(Inquiry, on_delete=models.CASCADE, related_name="admission")
    student = models.OneToOneField(
        "students.Student",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admission_record",
    )
    decision = models.CharField(max_length=20, choices=DECISION_CHOICES, default="pending")
    admitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admissions_granted",
    )
    admitted_at = models.DateTimeField(null=True, blank=True)

    def mark_admitted(self, *, user, student):
        self.student = student
        self.decision = "approved"
        self.admitted_by = user
        self.admitted_at = timezone.now()
        self.save(
            update_fields=["student", "decision", "admitted_by", "admitted_at"]
        )

    def __str__(self) -> str:
        return f"Admission for {self.inquiry_id}"
