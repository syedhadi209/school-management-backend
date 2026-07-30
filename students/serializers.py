from rest_framework import serializers

from academics.models import Section
from accounts.parent_services import provision_parent_for_student
from core.cnic import validate_cnic
from core.image_uploads import optimize_profile_image, schedule_storage_delete

from .models import ParentStudentLink, Student


class StudentSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    section_name = serializers.CharField(source="section.name", read_only=True, default=None)
    class_level_name = serializers.CharField(source="section.class_level.name", read_only=True, default=None)
    is_board_class = serializers.SerializerMethodField()
    parent_invite_pending = serializers.SerializerMethodField()
    profile_image_clear = serializers.BooleanField(write_only=True, required=False, default=False)

    def get_full_name(self, obj: Student) -> str:
        return f"{obj.first_name} {obj.last_name}".strip()

    def get_is_board_class(self, obj: Student) -> bool:
        section = obj.section
        if section is None:
            return False
        return bool(section.class_level.is_board_class)

    def get_parent_invite_pending(self, obj: Student) -> bool:
        link = obj.parent_links.select_related("parent__user").first()
        if link is None:
            return False
        return not link.parent.user.has_usable_password()

    class Meta:
        model = Student
        fields = "__all__"
        read_only_fields = ("school", "roll_number")
        extra_kwargs = {
            "board_roll_number": {"required": False, "allow_blank": True},
            "last_name": {"required": False, "allow_blank": True},
            "guardian_phone": {"required": False, "allow_blank": True},
            "parent_alternate_phone": {"required": False, "allow_blank": True},
            "parent_email": {"required": False, "allow_blank": True},
            "parent_occupation": {"required": False, "allow_blank": True},
            "father_name": {"required": False, "allow_blank": True},
            "mother_name": {"required": False, "allow_blank": True},
            "father_cnic": {"required": False, "allow_blank": True},
            "mother_cnic": {"required": False, "allow_blank": True},
            "address": {"required": False, "allow_blank": True},
            "region": {"required": False, "allow_blank": True},
            "gender": {"required": False, "allow_blank": True},
            "profile_image": {"required": False, "allow_null": True},
        }

    def validate_board_roll_number(self, value: str) -> str:
        return (value or "").strip()

    def validate_father_cnic(self, value: str) -> str:
        return validate_cnic(value)

    def validate_mother_cnic(self, value: str) -> str:
        return validate_cnic(value)

    def validate_parent_email(self, value: str) -> str:
        return (value or "").strip().lower()

    def validate_profile_image(self, value):
        return optimize_profile_image(value)

    def validate_section(self, section: Section | None) -> Section | None:
        if section is None:
            return None
        request = self.context.get("request")
        school = getattr(getattr(request, "user", None), "active_school", None)
        if school is not None and section.school_id != school.id:
            raise serializers.ValidationError("Section must belong to your active school.")
        return section

    def validate(self, attrs):
        instance = self.instance
        section = attrs.get("section", getattr(instance, "section", None))
        board_roll = attrs.get(
            "board_roll_number",
            getattr(instance, "board_roll_number", "") if instance else "",
        )
        board_roll = (board_roll or "").strip()
        attrs["board_roll_number"] = board_roll

        if board_roll:
            if section is None:
                raise serializers.ValidationError(
                    {
                        "board_roll_number": (
                            "Assign the student to a board class section before setting a board roll number."
                        )
                    }
                )
            class_level = section.class_level
            if not class_level.is_board_class:
                raise serializers.ValidationError(
                    {
                        "board_roll_number": (
                            f"{class_level.name} is not marked as a board examination class. "
                            "Enable board eligibility on the class first."
                        )
                    }
                )

            school = attrs.get("school") or getattr(instance, "school", None)
            if school is None:
                request = self.context.get("request")
                school = getattr(getattr(request, "user", None), "active_school", None)

            duplicate_qs = Student.objects.filter(school=school, board_roll_number=board_roll)
            if instance is not None:
                duplicate_qs = duplicate_qs.exclude(pk=instance.pk)
            if duplicate_qs.exists():
                raise serializers.ValidationError(
                    {
                        "board_roll_number": (
                            "This board roll number is already used by another student in this school."
                        )
                    }
                )

        return attrs

    def create(self, validated_data):
        validated_data.pop("profile_image_clear", None)
        student = super().create(validated_data)
        self._sync_parent(student)
        return student

    def update(self, instance, validated_data):
        clear_profile_image = validated_data.pop("profile_image_clear", False)
        old_image_name = instance.profile_image.name
        old_image_storage = instance.profile_image.storage if old_image_name else None

        if clear_profile_image:
            validated_data["profile_image"] = None

        student = super().update(instance, validated_data)
        new_image_name = student.profile_image.name
        if old_image_name and old_image_name != new_image_name and old_image_storage is not None:
            schedule_storage_delete(old_image_storage, old_image_name)
        self._sync_parent(student)
        return student

    def _sync_parent(self, student: Student) -> None:
        request = self.context.get("request")
        school = student.school or getattr(getattr(request, "user", None), "active_school", None)
        if school is None:
            return
        provision_parent_for_student(
            student=student,
            email=student.parent_email,
            school=school,
            relation="guardian",
            first_name=student.father_name or student.mother_name or "",
        )


class ParentStudentLinkSerializer(serializers.ModelSerializer):
    parent_name = serializers.CharField(source="parent.user.first_name", read_only=True, default="")
    student_name = serializers.SerializerMethodField()

    def get_student_name(self, obj: ParentStudentLink) -> str:
        return f"{obj.student.first_name} {obj.student.last_name}".strip()

    class Meta:
        model = ParentStudentLink
        fields = "__all__"
        read_only_fields = ("school",)
