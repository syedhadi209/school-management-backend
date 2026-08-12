from rest_framework.routers import DefaultRouter

from .views import FamilyViewSet

router = DefaultRouter()
router.register("families", FamilyViewSet, basename="families")

urlpatterns = router.urls
