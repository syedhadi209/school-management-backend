from rest_framework.routers import DefaultRouter

from .views import BillingInvoiceViewSet, PlanViewSet, SubscriptionViewSet

router = DefaultRouter()
router.register("plans", PlanViewSet, basename="plans")
router.register("subscriptions", SubscriptionViewSet, basename="subscriptions")
router.register("billing-invoices", BillingInvoiceViewSet, basename="billing-invoices")

urlpatterns = router.urls

