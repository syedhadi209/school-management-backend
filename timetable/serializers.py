from rest_framework import serializers

from .models import TimetableEntry


class TimetableEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = TimetableEntry
        fields = "__all__"

