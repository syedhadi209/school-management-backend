from rest_framework import serializers

from .models import ClassLevel, ClassSubject, PassingCriteria, Section, Subject, TeacherSubjectAssignment


class ClassLevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClassLevel
        fields = "__all__"


class SectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Section
        fields = "__all__"


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = "__all__"


class ClassSubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClassSubject
        fields = "__all__"


class TeacherSubjectAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeacherSubjectAssignment
        fields = "__all__"


class PassingCriteriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = PassingCriteria
        fields = "__all__"

