from rest_framework.routers import DefaultRouter

from .views import ParentStudentLinkViewSet, StudentViewSet

router = DefaultRouter()
router.register("students", StudentViewSet, basename="students")
router.register("parent-links", ParentStudentLinkViewSet, basename="parent-links")

urlpatterns = router.urls

