from rest_framework import serializers

from schools.services import get_or_create_default_academic_year

from .models import Fund
from .services import fund_invoice_summary


class FundSerializer(serializers.ModelSerializer):
    class_level_names = serializers.SerializerMethodField()
    academic_year_name = serializers.CharField(source="academic_year.name", read_only=True, default="")
    invoice_summary = serializers.SerializerMethodField()

    class Meta:
        model = Fund
        fields = (
            "id",
            "school",
            "academic_year",
            "academic_year_name",
            "name",
            "amount",
            "tenure",
            "class_levels",
            "class_level_names",
            "starts_on",
            "due_on",
            "status",
            "notes",
            "created_by",
            "created_at",
            "updated_at",
            "invoice_summary",
        )
        read_only_fields = ("school", "created_by", "created_at", "updated_at", "status")
        extra_kwargs = {
            "academic_year": {"required": False},
        }

    def get_class_level_names(self, obj: Fund) -> list[str]:
        return list(obj.class_levels.order_by("order", "name").values_list("name", flat=True))

    def get_invoice_summary(self, obj: Fund) -> dict:
        return fund_invoice_summary(obj)

    def validate_amount(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        return value

    def validate(self, attrs):
        request = self.context.get("request")
        school = getattr(getattr(request, "user", None), "active_school", None)
        academic_year = attrs.get("academic_year", getattr(self.instance, "academic_year", None))
        if academic_year is None and school is not None:
            attrs["academic_year"] = get_or_create_default_academic_year(school)
            academic_year = attrs["academic_year"]
        if school is not None and academic_year is not None and academic_year.school_id != school.id:
            raise serializers.ValidationError(
                {"academic_year": "Academic year must belong to your active school."}
            )
        class_levels = attrs.get("class_levels")
        if class_levels is not None and school is not None:
            for level in class_levels:
                if level.school_id != school.id:
                    raise serializers.ValidationError(
                        {"class_levels": "All classes must belong to your active school."}
                    )
        name = attrs.get("name", getattr(self.instance, "name", None))
        year = attrs.get("academic_year", getattr(self.instance, "academic_year", None))
        if school is not None and name and year is not None:
            qs = Fund.objects.filter(school=school, academic_year=year, name=name)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"name": "A fund with this name already exists for this academic year."}
                )
        return attrs

    def create(self, validated_data):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        class_levels = validated_data.pop("class_levels", [])
        fund = Fund.objects.create(
            **validated_data,
            created_by=user if getattr(user, "is_authenticated", False) else None,
        )
        if class_levels:
            fund.class_levels.set(class_levels)
        return fund

    def update(self, instance, validated_data):
        class_levels = validated_data.pop("class_levels", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if class_levels is not None:
            instance.class_levels.set(class_levels)
        return instance
