from rest_framework.permissions import IsAuthenticated

from core.permissions import IsSchoolAdmin
from core.viewsets import TenantScopedModelViewSet

from .models import FeeStructure, Invoice, Payment
from .serializers import FeeStructureSerializer, InvoiceSerializer, PaymentSerializer


class FeeStructureViewSet(TenantScopedModelViewSet):
    queryset = FeeStructure.objects.select_related("class_level").all()
    serializer_class = FeeStructureSerializer
    permission_classes = [IsAuthenticated, IsSchoolAdmin]
    search_fields = ["name", "class_level__name"]
    filterset_fields = ["class_level"]
    ordering_fields = ["name", "amount"]
    ordering = ["name"]


class InvoiceViewSet(TenantScopedModelViewSet):
    queryset = Invoice.objects.select_related("student", "fee_structure").all()
    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated, IsSchoolAdmin]
    search_fields = ["student__first_name", "student__last_name", "fee_structure__name"]
    filterset_fields = ["status", "student", "fee_structure"]
    ordering_fields = ["due_date", "total_amount", "paid_amount"]
    ordering = ["-due_date"]


class PaymentViewSet(TenantScopedModelViewSet):
    queryset = Payment.objects.select_related("invoice__student").all()
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated, IsSchoolAdmin]
    filterset_fields = ["invoice", "method"]
    ordering_fields = ["paid_on", "amount"]
    ordering = ["-paid_on"]
