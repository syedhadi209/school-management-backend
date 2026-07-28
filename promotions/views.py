from rest_framework.permissions import IsAuthenticated

from core.permissions import IsManager
from core.viewsets import TenantScopedModelViewSet

from .models import PromotionHistory
from .serializers import PromotionHistorySerializer


class PromotionHistoryViewSet(TenantScopedModelViewSet):
    queryset = PromotionHistory.objects.all()
    serializer_class = PromotionHistorySerializer
    permission_classes = [IsAuthenticated, IsManager]
