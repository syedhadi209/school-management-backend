from rest_framework import serializers

from academics.models import Section

from .models import ParentStudentLink, Student


class StudentSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    section_name = serializers.CharField(source="section.name", read_only=True, default=None)
    class_level_name = serializers.CharField(source="section.class_level.name", read_only=True, default=None)
    is_board_class = serializers.SerializerMethodField()

    def get_full_name(self, obj: Student) -> str:
        return f"{obj.first_name} {obj.last_name}".strip()

    def get_is_board_class(self, obj: Student) -> bool:
        section = obj.section
        if section is None:
            return False
        return bool(section.class_level.is_board_class)

    class Meta:
        model = Student
        fields = "__all__"
        read_only_fields = ("school", "roll_number")

    def validate_board_roll_number(self, value: str) -> str:
        return (value or "").strip()

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
                    {"board_roll_number": "Assign the student to a board class section before setting a board roll number."}
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
                    {"board_roll_number": "This board roll number is already used by another student in this school."}
                )

        return attrs


class ParentStudentLinkSerializer(serializers.ModelSerializer):
    parent_name = serializers.CharField(source="parent.user.first_name", read_only=True, default="")
    student_name = serializers.SerializerMethodField()

    def get_student_name(self, obj: ParentStudentLink) -> str:
        return f"{obj.student.first_name} {obj.student.last_name}".strip()

    class Meta:
        model = ParentStudentLink
        fields = "__all__"
        read_only_fields = ("school",)
