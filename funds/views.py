from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.permissions import IsManager
from core.viewsets import TenantScopedModelViewSet

from .models import Fund
from .serializers import FundSerializer
from .services import activate_fund, sync_fund_invoices


class FundViewSet(TenantScopedModelViewSet):
    queryset = Fund.objects.prefetch_related("class_levels").select_related("academic_year").all()
    serializer_class = FundSerializer
    permission_classes = [IsAuthenticated, IsManager]
    search_fields = ["name", "notes"]
    filterset_fields = ["status", "tenure", "academic_year", "class_levels"]
    ordering_fields = ["name", "amount", "due_on", "created_at", "status"]
    ordering = ["-created_at", "-id"]

    @action(detail=True, methods=["post"], url_path="activate")
    def activate(self, request, pk=None):
        fund = self.get_object()
        result = activate_fund(fund, user=request.user)
        data = self.get_serializer(fund).data
        data["sync"] = result
        return Response(data)

    @action(detail=True, methods=["post"], url_path="sync-charges")
    def sync_charges(self, request, pk=None):
        fund = self.get_object()
        result = sync_fund_invoices(fund)
        data = self.get_serializer(fund).data
        data["sync"] = result
        return Response(data)
