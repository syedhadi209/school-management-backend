from rest_framework.routers import DefaultRouter

from .views import AcademicYearViewSet, SchoolViewSet

router = DefaultRouter()
router.register("schools", SchoolViewSet, basename="schools")
router.register("academic-years", AcademicYearViewSet, basename="academic-years")

urlpatterns = router.urls

