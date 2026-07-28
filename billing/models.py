from django.db import models


class Plan(models.Model):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2)
    yearly_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    features = models.JSONField(default=dict, blank=True)


class Subscription(models.Model):
    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="subscriptions")
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="subscriptions")
    status = models.CharField(max_length=30, default="trial")
    stripe_subscription_id = models.CharField(max_length=100, blank=True)
    starts_on = models.DateField(null=True, blank=True)
    ends_on = models.DateField(null=True, blank=True)


class BillingInvoice(models.Model):
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name="invoices")
    external_id = models.CharField(max_length=100, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default="USD")
    status = models.CharField(max_length=20, default="pending")
    generated_at = models.DateTimeField(auto_now_add=True)
