from decimal import Decimal, InvalidOperation

from rest_framework import serializers

from academics.models import ClassLevel, Section
from core.cnic import validate_cnic
from core.image_uploads import optimize_profile_image
from students.models import Student

from .models import Admission, Inquiry, VisitorLog

APPLIED_REQUIRED_FIELDS = (
    "date_of_birth",
    "gender",
    "address",
    "parent_email",
)


class InquirySerializer(serializers.ModelSerializer):
    interested_class_name = serializers.CharField(
        source="interested_class_level.name", read_only=True, default=""
    )
    preferred_section_name = serializers.CharField(
        source="preferred_section.name", read_only=True, default=""
    )
    student_id = serializers.SerializerMethodField()
    student_roll_number = serializers.SerializerMethodField()

    class Meta:
        model = Inquiry
        fields = "__all__"
        read_only_fields = ("school", "created_at", "updated_at")

    def get_student_id(self, obj: Inquiry):
        try:
            admission = obj.admission
        except Admission.DoesNotExist:
            return None
        if admission.student_id is None:
            return None
        return admission.student_id

    def get_student_roll_number(self, obj: Inquiry):
        try:
            admission = obj.admission
        except Admission.DoesNotExist:
            return ""
        if admission.student is None:
            return ""
        return admission.student.roll_number

    def validate_father_cnic(self, value: str) -> str:
        return validate_cnic(value)

    def validate_mother_cnic(self, value: str) -> str:
        return validate_cnic(value)

    def validate_parent_email(self, value: str) -> str:
        return (value or "").strip().lower()

    def validate_email(self, value: str) -> str:
        return (value or "").strip().lower()

    def validate_profile_image(self, value):
        return optimize_profile_image(value)

    def validate_family_lookup_code(self, value: str) -> str:
        return (value or "").strip().upper()

    def validate_interested_class_level(self, class_level: ClassLevel | None) -> ClassLevel | None:
        if class_level is None:
            return None
        school = self._active_school()
        if school is not None and class_level.school_id != school.id:
            raise serializers.ValidationError("Class must belong to your active school.")
        return class_level

    def validate_preferred_section(self, section: Section | None) -> Section | None:
        if section is None:
            return None
        school = self._active_school()
        if school is not None and section.school_id != school.id:
            raise serializers.ValidationError("Section must belong to your active school.")
        return section

    def validate(self, attrs):
        instance = self.instance
        status = attrs.get("status", getattr(instance, "status", "new"))

        if status == "admitted" and (instance is None or instance.status != "admitted"):
            raise serializers.ValidationError(
                {
                    "status": (
                        "Use the Admit & Enrol action to mark an inquiry as admitted. "
                        "Status cannot be set to admitted directly."
                    )
                }
            )

        if status == "rejected":
            reason = attrs.get(
                "rejection_reason",
                getattr(instance, "rejection_reason", "") if instance else "",
            )
            if not (reason or "").strip():
                raise serializers.ValidationError(
                    {"rejection_reason": "Provide a rejection reason when rejecting an inquiry."}
                )

        full_name = attrs.get("full_name", getattr(instance, "full_name", "") if instance else "")
        first_name = attrs.get("first_name", getattr(instance, "first_name", "") if instance else "")
        if not (full_name or "").strip() and not (first_name or "").strip():
            raise serializers.ValidationError({"full_name": "Prospective student name is required."})

        phone = attrs.get("phone", getattr(instance, "phone", "") if instance else "")
        email = attrs.get("email", getattr(instance, "email", "") if instance else "")
        parent_email = attrs.get(
            "parent_email", getattr(instance, "parent_email", "") if instance else ""
        )
        parent_phone = attrs.get(
            "parent_phone", getattr(instance, "parent_phone", "") if instance else ""
        )
        if instance is None:
            has_contact = any(
                (value or "").strip() for value in (phone, email, parent_email, parent_phone)
            )
            if not has_contact:
                raise serializers.ValidationError(
                    {"phone": "Provide a phone number or email for the inquiry."}
                )

        if status == "applied":
            errors = {}
            for field in APPLIED_REQUIRED_FIELDS:
                value = attrs.get(field, getattr(instance, field, None) if instance else None)
                if value in (None, ""):
                    errors[field] = "This field is required for an applied inquiry."
            father = attrs.get("father_name", getattr(instance, "father_name", "") if instance else "")
            mother = attrs.get("mother_name", getattr(instance, "mother_name", "") if instance else "")
            if not (father or "").strip() and not (mother or "").strip():
                errors["father_name"] = "Provide at least a father or mother name for an applied inquiry."
            if errors:
                raise serializers.ValidationError(errors)

        preferred_section = attrs.get(
            "preferred_section", getattr(instance, "preferred_section", None) if instance else None
        )
        interested_class = attrs.get(
            "interested_class_level",
            getattr(instance, "interested_class_level", None) if instance else None,
        )
        if preferred_section is not None and interested_class is not None:
            if preferred_section.class_level_id != interested_class.id:
                raise serializers.ValidationError(
                    {"preferred_section": "Preferred section must belong to the interested class."}
                )

        return attrs

    def _active_school(self):
        request = self.context.get("request")
        return getattr(getattr(request, "user", None), "active_school", None)


class AdmitInquirySerializer(serializers.Serializer):
    section = serializers.PrimaryKeyRelatedField(queryset=Section.objects.all())
    admission_date = serializers.DateField(required=False, allow_null=True)
    student_status = serializers.CharField(required=False, default="active")

    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    gender = serializers.ChoiceField(choices=Student.GENDER_CHOICES, required=False, allow_blank=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    guardian_phone = serializers.CharField(required=False, allow_blank=True)
    parent_alternate_phone = serializers.CharField(required=False, allow_blank=True)
    parent_email = serializers.EmailField(required=False, allow_blank=True)
    parent_occupation = serializers.CharField(required=False, allow_blank=True)
    father_name = serializers.CharField(required=False, allow_blank=True)
    mother_name = serializers.CharField(required=False, allow_blank=True)
    father_cnic = serializers.CharField(required=False, allow_blank=True)
    mother_cnic = serializers.CharField(required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)
    region = serializers.CharField(required=False, allow_blank=True)
    board_roll_number = serializers.CharField(required=False, allow_blank=True)
    profile_image = serializers.ImageField(required=False, allow_null=True)
    discount_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    fee_notes = serializers.CharField(required=False, allow_blank=True)
    family_lookup_code = serializers.CharField(required=False, allow_blank=True)

    def validate_family_lookup_code(self, value: str) -> str:
        return (value or "").strip().upper()

    def validate_discount_amount(self, value):
        if value is None:
            return None
        try:
            amount = Decimal(value)
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise serializers.ValidationError("Enter a valid discount amount.") from exc
        if amount < 0:
            raise serializers.ValidationError("Discount cannot be negative.")
        return amount

    def validate_student_status(self, value: str) -> str:
        allowed = {choice[0] for choice in Student.STATUS_CHOICES}
        if value not in allowed:
            raise serializers.ValidationError("Invalid student status.")
        return value

    def validate_father_cnic(self, value: str) -> str:
        return validate_cnic(value)

    def validate_mother_cnic(self, value: str) -> str:
        return validate_cnic(value)

    def validate_parent_email(self, value: str) -> str:
        return (value or "").strip().lower()

    def validate_profile_image(self, value):
        return optimize_profile_image(value)

    def validate_section(self, section: Section) -> Section:
        request = self.context.get("request")
        school = getattr(getattr(request, "user", None), "active_school", None)
        if school is not None and section.school_id != school.id:
            raise serializers.ValidationError("Section must belong to your active school.")
        return section


class VisitorLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = VisitorLog
        fields = "__all__"
        read_only_fields = ("school",)


class AdmissionSerializer(serializers.ModelSerializer):
    inquiry_name = serializers.CharField(source="inquiry.full_name", read_only=True, default="")
    student_name = serializers.SerializerMethodField()
    student_roll_number = serializers.CharField(source="student.roll_number", read_only=True, default="")
    admitted_by_email = serializers.CharField(source="admitted_by.email", read_only=True, default="")

    def get_student_name(self, obj: Admission) -> str:
        if not obj.student:
            return ""
        return f"{obj.student.first_name} {obj.student.last_name}".strip()

    class Meta:
        model = Admission
        fields = "__all__"
        read_only_fields = ("school", "admitted_by", "admitted_at")
