from rest_framework.permissions import SAFE_METHODS, IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action

from core.permissions import IsManager, IsSchoolAdmin, get_active_role
from core.viewsets import TenantScopedModelViewSet

from .models import FeeStructure, Invoice, Payment
from .serializers import FeeStructureSerializer, InvoiceSerializer, PaymentSerializer


class FeeStructureViewSet(TenantScopedModelViewSet):
    queryset = FeeStructure.objects.select_related("class_level").all()
    serializer_class = FeeStructureSerializer
    search_fields = ["name", "class_level__name"]
    filterset_fields = ["class_level"]
    ordering_fields = ["name", "amount", "class_level__order", "class_level__name"]
    ordering = ["class_level__order", "class_level__name", "id"]

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            # Managers need read access when creating/editing students.
            return [IsAuthenticated(), IsManager()]
        return [IsAuthenticated(), IsSchoolAdmin()]

    @action(detail=False, methods=["get"], url_path="for-class")
    def for_class(self, request):
        class_level_id = request.query_params.get("class_level")
        if not class_level_id:
            return Response({"detail": "class_level query param is required."}, status=400)
        fee = self.get_queryset().filter(class_level_id=class_level_id).first()
        if fee is None:
            return Response({"detail": "No monthly tuition set for this class."}, status=404)
        return Response(self.get_serializer(fee).data)


class InvoiceViewSet(TenantScopedModelViewSet):
    queryset = Invoice.objects.select_related(
        "student", "fee_structure", "fund"
    ).all()
    serializer_class = InvoiceSerializer
    search_fields = [
        "student__first_name",
        "student__last_name",
        "fee_structure__name",
        "fund__name",
    ]
    filterset_fields = ["status", "student", "fee_structure", "invoice_type", "fund"]
    ordering_fields = ["due_date", "total_amount", "paid_amount", "invoice_type"]
    ordering = ["-due_date", "-id"]

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsManager()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser:
            return qs
        role = get_active_role(user)
        if role == "parent":
            parent = getattr(user, "parent_profile", None)
            if parent is None:
                return qs.none()
            return qs.filter(student__parent_links__parent=parent).distinct()
        if role in {"school_admin", "manager"}:
            return qs
        return qs.none()


class PaymentViewSet(TenantScopedModelViewSet):
    queryset = Payment.objects.select_related("invoice__student", "invoice__fund").all()
    serializer_class = PaymentSerializer
    filterset_fields = ["invoice", "method"]
    ordering_fields = ["paid_on", "amount"]
    ordering = ["-paid_on"]

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticated(), IsManager()]
        return [IsAuthenticated(), IsManager()]
