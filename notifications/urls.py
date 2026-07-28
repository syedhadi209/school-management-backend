from rest_framework.routers import DefaultRouter

from .views import AnnouncementViewSet, NotificationViewSet

router = DefaultRouter()
router.register("notifications", NotificationViewSet, basename="notifications")
router.register("announcements", AnnouncementViewSet, basename="announcements")

urlpatterns = router.urls

