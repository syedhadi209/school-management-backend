from rest_framework.routers import DefaultRouter

from .views import AttendanceRecordViewSet, AttendanceSessionViewSet

router = DefaultRouter()
router.register("attendance-sessions", AttendanceSessionViewSet, basename="attendance-sessions")
router.register("attendance-records", AttendanceRecordViewSet, basename="attendance-records")

urlpatterns = router.urls
