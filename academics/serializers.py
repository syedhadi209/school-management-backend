from rest_framework import serializers

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
    class_teacher_name = serializers.CharField(source="class_teacher.user.first_name", read_only=True, default="")
    is_board_class = serializers.BooleanField(source="class_level.is_board_class", read_only=True, default=False)
    student_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Section
        fields = "__all__"
        read_only_fields = ("school",)

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
            raise serializers.ValidationError("Teacher must belong to your active school.")
        return class_teacher


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


class PassingCriteriaSerializer(serializers.ModelSerializer):
    class_level_name = serializers.CharField(source="class_level.name", read_only=True, default="")

    class Meta:
        model = PassingCriteria
        fields = "__all__"
        read_only_fields = ("school",)

