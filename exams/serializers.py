from decimal import Decimal

from rest_framework import serializers

from academics.models import Section, Subject
from schools.models import AcademicYear
from schools.services import get_or_create_default_academic_year
from timetable.services import section_label

from .models import Exam, ExamSchedule, ExamSheet, Mark, MarkSheet
from .services import (
    create_class_test,
    create_term_exam,
    sheet_completion_summary,
    sheet_summary,
)


class ExamSerializer(serializers.ModelSerializer):
    academic_year = serializers.PrimaryKeyRelatedField(
        queryset=AcademicYear.objects.all(), required=False, allow_null=True
    )
    section = serializers.PrimaryKeyRelatedField(
        queryset=Section.objects.all(), required=False, allow_null=True
    )
    subject = serializers.PrimaryKeyRelatedField(
        queryset=Subject.objects.all(), required=False, allow_null=True
    )
    exam_type = serializers.ChoiceField(choices=Exam.TYPE_CHOICES, required=False, default=Exam.TYPE_CLASS_TEST)
    section_label = serializers.SerializerMethodField()
    subject_name = serializers.CharField(source="subject.name", read_only=True, default="")
    created_by_name = serializers.SerializerMethodField()
    published_by_name = serializers.SerializerMethodField()
    completion = serializers.SerializerMethodField()

    class Meta:
        model = Exam
        fields = (
            "id",
            "school",
            "academic_year",
            "name",
            "exam_type",
            "status",
            "section",
            "section_label",
            "subject",
            "subject_name",
            "max_marks",
            "starts_on",
            "ends_on",
            "created_by",
            "created_by_name",
            "published_at",
            "published_by",
            "published_by_name",
            "created_at",
            "updated_at",
            "completion",
        )
        read_only_fields = (
            "school",
            "created_by",
            "published_at",
            "published_by",
            "created_at",
            "updated_at",
            "status",
        )
        # Uniqueness is enforced in create_class_test / create_term_exam services.
        # DRF's UniqueConstraint validators incorrectly require nullable scope fields.
        validators = []

    def get_section_label(self, obj: Exam) -> str:
        if obj.section_id is None:
            return ""
        return section_label(obj.section)

    def get_created_by_name(self, obj: Exam) -> str:
        if obj.created_by_id is None:
            return ""
        name = f"{obj.created_by.first_name} {obj.created_by.last_name}".strip()
        return name or obj.created_by.email

    def get_published_by_name(self, obj: Exam) -> str:
        if obj.published_by_id is None:
            return ""
        name = f"{obj.published_by.first_name} {obj.published_by.last_name}".strip()
        return name or obj.published_by.email

    def get_completion(self, obj: Exam) -> dict:
        return sheet_completion_summary(obj)

    def create(self, validated_data):
        request = self.context["request"]
        school = request.user.active_school
        exam_type = validated_data.get("exam_type", Exam.TYPE_CLASS_TEST)
        academic_year = validated_data.get("academic_year") or get_or_create_default_academic_year(school)

        if exam_type == Exam.TYPE_CLASS_TEST:
            section = validated_data.get("section")
            subject = validated_data.get("subject")
            if section is None or subject is None:
                raise serializers.ValidationError(
                    {"detail": "Class tests require section and subject."}
                )
            return create_class_test(
                user=request.user,
                school=school,
                name=validated_data["name"],
                section=section,
                subject=subject,
                max_marks=validated_data.get("max_marks"),
                starts_on=validated_data.get("starts_on"),
                ends_on=validated_data.get("ends_on"),
                academic_year=academic_year,
            )

        return create_term_exam(
            user=request.user,
            school=school,
            name=validated_data["name"],
            exam_type=exam_type,
            max_marks=validated_data.get("max_marks"),
            starts_on=validated_data.get("starts_on"),
            ends_on=validated_data.get("ends_on"),
            academic_year=academic_year,
        )


class ExamScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamSchedule
        fields = "__all__"
        read_only_fields = ("school",)


class ExamSheetSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamSheet
        fields = "__all__"
        read_only_fields = ("school",)


class MarkRecordSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    roll_number = serializers.CharField(source="student.roll_number", read_only=True, default="")
    subject_name = serializers.CharField(source="subject.name", read_only=True, default="")
    exam_name = serializers.CharField(source="exam.name", read_only=True, default="")
    exam_type = serializers.CharField(source="exam.exam_type", read_only=True, default="")
    exam_status = serializers.CharField(source="exam.status", read_only=True, default="")
    percentage = serializers.SerializerMethodField()

    class Meta:
        model = Mark
        fields = (
            "id",
            "school",
            "exam",
            "exam_name",
            "exam_type",
            "exam_status",
            "sheet",
            "student",
            "student_name",
            "roll_number",
            "subject",
            "subject_name",
            "teacher",
            "marks_obtained",
            "max_marks",
            "remarks",
            "percentage",
            "marked_at",
        )
        read_only_fields = fields

    def get_student_name(self, obj: Mark) -> str:
        return f"{obj.student.first_name} {obj.student.last_name}".strip()

    def get_percentage(self, obj: Mark) -> float | None:
        if not obj.max_marks:
            return None
        return float((obj.marks_obtained / obj.max_marks * 100).quantize(Decimal("0.01")))


class MarkSheetSerializer(serializers.ModelSerializer):
    section_label = serializers.SerializerMethodField()
    subject_name = serializers.CharField(source="subject.name", read_only=True, default="")
    teacher_name = serializers.SerializerMethodField()
    exam_name = serializers.CharField(source="exam.name", read_only=True, default="")
    exam_type = serializers.CharField(source="exam.exam_type", read_only=True, default="")
    exam_status = serializers.CharField(source="exam.status", read_only=True, default="")
    summary = serializers.SerializerMethodField()
    marks = MarkRecordSerializer(many=True, read_only=True)

    class Meta:
        model = MarkSheet
        fields = (
            "id",
            "school",
            "academic_year",
            "exam",
            "exam_name",
            "exam_type",
            "exam_status",
            "section",
            "section_label",
            "subject",
            "subject_name",
            "teacher",
            "teacher_name",
            "status",
            "max_marks",
            "notes",
            "submitted_at",
            "submitted_by",
            "created_at",
            "updated_at",
            "summary",
            "marks",
        )
        read_only_fields = fields

    def get_section_label(self, obj: MarkSheet) -> str:
        return section_label(obj.section)

    def get_teacher_name(self, obj: MarkSheet) -> str:
        if obj.teacher_id is None:
            return ""
        name = f"{obj.teacher.user.first_name} {obj.teacher.user.last_name}".strip()
        return name or obj.teacher.user.email

    def get_summary(self, obj: MarkSheet) -> dict:
        return sheet_summary(obj)


class MarkSheetListSerializer(MarkSheetSerializer):
    class Meta(MarkSheetSerializer.Meta):
        fields = tuple(f for f in MarkSheetSerializer.Meta.fields if f != "marks")


class MarkEnterRecordSerializer(serializers.Serializer):
    student = serializers.IntegerField(min_value=1)
    marks_obtained = serializers.DecimalField(max_digits=6, decimal_places=2)
    remarks = serializers.CharField(required=False, allow_blank=True, max_length=255, default="")


class MarkEnterSerializer(serializers.Serializer):
    exam = serializers.IntegerField(min_value=1)
    section = serializers.IntegerField(min_value=1)
    subject = serializers.IntegerField(min_value=1)
    max_marks = serializers.DecimalField(
        max_digits=6, decimal_places=2, required=False, allow_null=True
    )
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    records = MarkEnterRecordSerializer(many=True)
