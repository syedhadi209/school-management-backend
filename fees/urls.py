from rest_framework.routers import DefaultRouter

from .views import FeeStructureViewSet, InvoiceViewSet, PaymentViewSet

router = DefaultRouter()
router.register("fee-structures", FeeStructureViewSet, basename="fee-structures")
router.register("invoices", InvoiceViewSet, basename="invoices")
router.register("payments", PaymentViewSet, basename="payments")

urlpatterns = router.urls

