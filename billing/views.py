from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from core.permissions import IsSuperAdmin

from .models import BillingInvoice, Plan, Subscription
from .serializers import BillingInvoiceSerializer, PlanSerializer, SubscriptionSerializer


class PlanViewSet(ModelViewSet):
    queryset = Plan.objects.all()
    serializer_class = PlanSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin]


class SubscriptionViewSet(ModelViewSet):
    queryset = Subscription.objects.all()
    serializer_class = SubscriptionSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin]


class BillingInvoiceViewSet(ModelViewSet):
    queryset = BillingInvoice.objects.all()
    serializer_class = BillingInvoiceSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin]
