from rest_framework.permissions import IsAuthenticated

from core.permissions import IsManager
from core.viewsets import TenantScopedModelViewSet

from .models import Admission, Inquiry, VisitorLog
from .serializers import AdmissionSerializer, InquirySerializer, VisitorLogSerializer


class InquiryViewSet(TenantScopedModelViewSet):
    queryset = Inquiry.objects.all()
    serializer_class = InquirySerializer
    permission_classes = [IsAuthenticated, IsManager]


class VisitorLogViewSet(TenantScopedModelViewSet):
    queryset = VisitorLog.objects.all()
    serializer_class = VisitorLogSerializer
    permission_classes = [IsAuthenticated, IsManager]


class AdmissionViewSet(TenantScopedModelViewSet):
    queryset = Admission.objects.all()
    serializer_class = AdmissionSerializer
    permission_classes = [IsAuthenticated, IsManager]
