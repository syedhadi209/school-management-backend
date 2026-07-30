from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.permissions import IsManager
from core.viewsets import TenantScopedModelViewSet

from .models import Admission, Inquiry, VisitorLog
from .serializers import (
    AdmissionSerializer,
    AdmitInquirySerializer,
    InquirySerializer,
    VisitorLogSerializer,
)
from .services import admit_and_enrol
from students.serializers import StudentSerializer


class InquiryViewSet(TenantScopedModelViewSet):
    queryset = Inquiry.objects.select_related(
        "interested_class_level",
        "preferred_section",
        "admission",
        "admission__student",
    ).all()
    serializer_class = InquirySerializer
    permission_classes = [IsAuthenticated, IsManager]
    search_fields = [
        "full_name",
        "first_name",
        "last_name",
        "phone",
        "email",
        "parent_email",
        "interested_class",
        "source",
        "father_name",
        "mother_name",
    ]
    filterset_fields = ["status", "source", "interested_class_level", "preferred_section"]
    ordering_fields = ["full_name", "created_at", "id", "follow_up_date"]
    ordering = ["-id"]

    @action(detail=True, methods=["post"], url_path="admit")
    def admit(self, request, pk=None):
        inquiry = self.get_object()
        serializer = AdmitInquirySerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        student, admission, created = admit_and_enrol(
            inquiry=inquiry,
            section=serializer.validated_data["section"],
            acting_user=request.user,
            admission_date=serializer.validated_data.get("admission_date"),
            student_status=serializer.validated_data.get("student_status", "active"),
        )

        return Response(
            {
                "created": created,
                "student": StudentSerializer(student, context={"request": request}).data,
                "admission": AdmissionSerializer(admission, context={"request": request}).data,
                "inquiry": InquirySerializer(
                    Inquiry.objects.select_related(
                        "interested_class_level",
                        "preferred_section",
                        "admission",
                        "admission__student",
                    ).get(pk=inquiry.pk),
                    context={"request": request},
                ).data,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class VisitorLogViewSet(TenantScopedModelViewSet):
    queryset = VisitorLog.objects.all()
    serializer_class = VisitorLogSerializer
    permission_classes = [IsAuthenticated, IsManager]
    search_fields = ["visitor_name", "purpose", "met_with"]
    ordering_fields = ["check_in", "check_out"]
    ordering = ["-check_in"]


class AdmissionViewSet(TenantScopedModelViewSet):
    queryset = Admission.objects.select_related("inquiry", "student", "admitted_by").all()
    serializer_class = AdmissionSerializer
    permission_classes = [IsAuthenticated, IsManager]
    search_fields = ["inquiry__full_name", "student__first_name", "student__last_name"]
    filterset_fields = ["decision", "student"]
    ordering_fields = ["id", "admitted_at"]
    ordering = ["-id"]
