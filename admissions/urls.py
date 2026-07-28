from rest_framework.routers import DefaultRouter

from .views import AdmissionViewSet, InquiryViewSet, VisitorLogViewSet

router = DefaultRouter()
router.register("inquiries", InquiryViewSet, basename="inquiries")
router.register("visitor-logs", VisitorLogViewSet, basename="visitor-logs")
router.register("admissions", AdmissionViewSet, basename="admissions")

urlpatterns = router.urls

