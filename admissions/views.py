from rest_framework.permissions import IsAuthenticated

from core.permissions import IsManager
from core.viewsets import TenantScopedModelViewSet

from .models import Admission, Inquiry, VisitorLog
from .serializers import AdmissionSerializer, InquirySerializer, VisitorLogSerializer


class InquiryViewSet(TenantScopedModelViewSet):
    queryset = Inquiry.objects.all()
    serializer_class = InquirySerializer
    permission_classes = [IsAuthenticated, IsManager]
    search_fields = ["full_name", "phone", "interested_class", "source"]
    filterset_fields = ["status", "source"]
    ordering_fields = ["full_name", "id"]
    ordering = ["-id"]


class VisitorLogViewSet(TenantScopedModelViewSet):
    queryset = VisitorLog.objects.all()
    serializer_class = VisitorLogSerializer
    permission_classes = [IsAuthenticated, IsManager]
    search_fields = ["visitor_name", "purpose", "met_with"]
    ordering_fields = ["check_in", "check_out"]
    ordering = ["-check_in"]


class AdmissionViewSet(TenantScopedModelViewSet):
    queryset = Admission.objects.select_related("inquiry", "student").all()
    serializer_class = AdmissionSerializer
    permission_classes = [IsAuthenticated, IsManager]
    search_fields = ["inquiry__full_name", "student__first_name", "student__last_name"]
    filterset_fields = ["decision", "student"]
    ordering_fields = ["id"]
    ordering = ["-id"]
