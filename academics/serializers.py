from django.db import transaction
from rest_framework import serializers

from accounts.models import TeacherProfile
from schools.services import get_or_create_default_academic_year

from .models import ClassLevel, ClassSubject, PassingCriteria, Section, Subject, TeacherSubjectAssignment


class ClassLevelSerializer(serializers.ModelSerializer):
    academic_year_name = serializers.CharField(source="academic_year.name", read_only=True, default="")
    section_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = ClassLevel
        fields = "__all__"
        read_only_fields = ("school",)
        extra_kwargs = {
            # Defaults to the school's active academic year when omitted.
            "academic_year": {"required": False},
        }

    def validate_academic_year(self, academic_year):
        request = self.context.get("request")
        school = getattr(getattr(request, "user", None), "active_school", None)
        if school is not None and academic_year.school_id != school.id:
            raise serializers.ValidationError("Academic year must belong to your active school.")
        return academic_year


class SectionSerializer(serializers.ModelSerializer):
    class_level_name = serializers.CharField(source="class_level.name", read_only=True, default="")
    class_teacher_name = serializers.SerializerMethodField()
    is_board_class = serializers.BooleanField(source="class_level.is_board_class", read_only=True, default=False)
    student_count = serializers.IntegerField(read_only=True, default=0)
    teachers = serializers.PrimaryKeyRelatedField(
        queryset=TeacherProfile.objects.all(),
        many=True,
        required=False,
    )
    teacher_names = serializers.SerializerMethodField()

    def get_class_teacher_name(self, obj: Section) -> str:
        if obj.class_teacher is None:
            return ""
        return f"{obj.class_teacher.user.first_name} {obj.class_teacher.user.last_name}".strip()

    def get_teacher_names(self, obj: Section) -> list[str]:
        names = []
        for teacher in obj.teachers.select_related("user").all():
            name = f"{teacher.user.first_name} {teacher.user.last_name}".strip()
            names.append(name or teacher.user.email)
        return names

    class Meta:
        model = Section
        fields = "__all__"
        read_only_fields = ("school", "teacher_names")
        extra_kwargs = {
            "class_teacher": {"required": False, "allow_null": True},
        }

    def validate_class_level(self, class_level: ClassLevel) -> ClassLevel:
        request = self.context.get("request")
        school = getattr(getattr(request, "user", None), "active_school", None)
        if school is not None and class_level.school_id != school.id:
            raise serializers.ValidationError("Class must belong to your active school.")
        return class_level

    def validate_class_teacher(self, class_teacher):
        if class_teacher is None:
            return None
        request = self.context.get("request")
        school = getattr(getattr(request, "user", None), "active_school", None)
        if school is not None and class_teacher.school_id != school.id:
            raise serializers.ValidationError("Class incharge must belong to your active school.")
        return class_teacher

    def validate_teachers(self, teachers):
        request = self.context.get("request")
        school = getattr(getattr(request, "user", None), "active_school", None)
        if school is None:
            return teachers
        for teacher in teachers:
            if teacher.school_id != school.id:
                raise serializers.ValidationError(
                    f"{teacher.user.first_name} does not belong to your active school."
                )
        return teachers

    def validate(self, attrs):
        class_teacher = attrs.get(
            "class_teacher",
            getattr(self.instance, "class_teacher", None) if self.instance else None,
        )
        teachers = attrs.get("teachers")
        if teachers is None and self.instance is not None:
            teachers = list(self.instance.teachers.all())
        elif teachers is None:
            teachers = []

        # If a class incharge is set and teachers were provided, ensure they are included.
        if class_teacher is not None and "teachers" in attrs:
            teacher_ids = {teacher.id for teacher in teachers}
            if class_teacher.id not in teacher_ids:
                teachers = list(teachers) + [class_teacher]
                attrs["teachers"] = teachers
        return attrs

    def create(self, validated_data):
        teachers = validated_data.pop("teachers", [])
        with transaction.atomic():
            section = Section.objects.create(**validated_data)
            if section.class_teacher_id and section.class_teacher not in teachers:
                teachers = list(teachers) + [section.class_teacher]
            if teachers:
                section.teachers.set(teachers)
        return section

    def update(self, instance, validated_data):
        teachers = validated_data.pop("teachers", None)
        with transaction.atomic():
            section = super().update(instance, validated_data)
            if teachers is not None:
                if section.class_teacher_id and section.class_teacher not in teachers:
                    teachers = list(teachers) + [section.class_teacher]
                section.teachers.set(teachers)
        return section

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["teachers"] = list(instance.teachers.values_list("id", flat=True))
        return data


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = "__all__"
        read_only_fields = ("school",)


class ClassSubjectSerializer(serializers.ModelSerializer):
    class_level_name = serializers.CharField(source="class_level.name", read_only=True, default="")
    subject_name = serializers.CharField(source="subject.name", read_only=True, default="")

    class Meta:
        model = ClassSubject
        fields = "__all__"
        read_only_fields = ("school",)


class TeacherSubjectAssignmentSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source="teacher.user.first_name", read_only=True, default="")
    subject_name = serializers.CharField(source="subject.name", read_only=True, default="")
    section_name = serializers.CharField(source="section.name", read_only=True, default="")

    class Meta:
        model = TeacherSubjectAssignment
        fields = "__all__"
        read_only_fields = ("school",)

    def validate(self, attrs):
        request = self.context.get("request")
        school = getattr(getattr(request, "user", None), "active_school", None)
        teacher = attrs.get("teacher", getattr(self.instance, "teacher", None))
        subject = attrs.get("subject", getattr(self.instance, "subject", None))
        section = attrs.get("section", getattr(self.instance, "section", None))
        academic_year = attrs.get("academic_year", getattr(self.instance, "academic_year", None))

        if school is not None:
            for label, obj in (
                ("teacher", teacher),
                ("subject", subject),
                ("section", section),
                ("academic_year", academic_year),
            ):
                if obj is not None and getattr(obj, "school_id", None) != school.id:
                    raise serializers.ValidationError(
                        {label: f"{label.replace('_', ' ').title()} must belong to your active school."}
                    )

        if academic_year is None and school is not None:
            attrs["academic_year"] = get_or_create_default_academic_year(school)

        return attrs


class PassingCriteriaSerializer(serializers.ModelSerializer):
    class_level_name = serializers.CharField(source="class_level.name", read_only=True, default="")

    class Meta:
        model = PassingCriteria
        fields = "__all__"
        read_only_fields = ("school",)
