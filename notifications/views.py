from rest_framework.permissions import IsAuthenticated

from core.viewsets import TenantScopedModelViewSet

from .models import Announcement, Notification
from .serializers import AnnouncementSerializer, NotificationSerializer


class NotificationViewSet(TenantScopedModelViewSet):
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]


class AnnouncementViewSet(TenantScopedModelViewSet):
    queryset = Announcement.objects.all()
    serializer_class = AnnouncementSerializer
    permission_classes = [IsAuthenticated]
