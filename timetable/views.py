from rest_framework.permissions import IsAuthenticated

from core.permissions import IsManager
from core.viewsets import TenantScopedModelViewSet

from .models import TimetableEntry
from .serializers import TimetableEntrySerializer


class TimetableEntryViewSet(TenantScopedModelViewSet):
    queryset = TimetableEntry.objects.all()
    serializer_class = TimetableEntrySerializer
    permission_classes = [IsAuthenticated, IsManager]
