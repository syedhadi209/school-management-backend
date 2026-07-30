from rest_framework import serializers

from .models import Admission, Inquiry, VisitorLog


class InquirySerializer(serializers.ModelSerializer):
    class Meta:
        model = Inquiry
        fields = "__all__"
        read_only_fields = ("school",)


class VisitorLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = VisitorLog
        fields = "__all__"
        read_only_fields = ("school",)


class AdmissionSerializer(serializers.ModelSerializer):
    inquiry_name = serializers.CharField(source="inquiry.full_name", read_only=True, default="")
    student_name = serializers.SerializerMethodField()

    def get_student_name(self, obj: Admission) -> str:
        if not obj.student:
            return ""
        return f"{obj.student.first_name} {obj.student.last_name}".strip()

    class Meta:
        model = Admission
        fields = "__all__"
        read_only_fields = ("school",)

