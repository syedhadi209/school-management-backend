from rest_framework import serializers

from .models import PromotionHistory


class PromotionHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PromotionHistory
        fields = "__all__"

