from rest_framework.routers import DefaultRouter

from .views import PromotionHistoryViewSet

router = DefaultRouter()
router.register("promotion-history", PromotionHistoryViewSet, basename="promotion-history")

urlpatterns = router.urls

