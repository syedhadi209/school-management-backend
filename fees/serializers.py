from decimal import Decimal

from rest_framework import serializers

from .models import FeeStructure, Invoice, Payment, StudentMonthlyFee


class FeeStructureSerializer(serializers.ModelSerializer):
    class_level_name = serializers.CharField(source="class_level.name", read_only=True, default="")

    class Meta:
        model = FeeStructure
        fields = "__all__"
        read_only_fields = ("school",)
        validators = []

    def validate(self, attrs):
        request = self.context.get("request")
        school = getattr(getattr(request, "user", None), "active_school", None)
        class_level = attrs.get("class_level", getattr(self.instance, "class_level", None))
        if school is not None and class_level is not None:
            qs = FeeStructure.objects.filter(school=school, class_level=class_level)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {
                        "class_level": (
                            f"{class_level.name} already has a monthly tuition. "
                            "Edit the existing fee instead of creating another."
                        )
                    }
                )
            if class_level.school_id != school.id:
                raise serializers.ValidationError(
                    {"class_level": "Class must belong to your active school."}
                )
        if "name" in attrs and not (attrs.get("name") or "").strip():
            attrs["name"] = "Monthly Tuition"
        return attrs


class StudentMonthlyFeeSerializer(serializers.ModelSerializer):
    effective_amount = serializers.SerializerMethodField()

    class Meta:
        model = StudentMonthlyFee
        fields = (
            "id",
            "student",
            "fee_structure",
            "base_amount",
            "discount_amount",
            "effective_amount",
            "notes",
            "updated_at",
        )
        read_only_fields = ("id", "student", "fee_structure", "base_amount", "updated_at")

    def get_effective_amount(self, obj: StudentMonthlyFee):
        return obj.effective_amount


class InvoiceSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    fee_structure_name = serializers.CharField(source="fee_structure.name", read_only=True, default="")
    balance = serializers.SerializerMethodField()

    def get_student_name(self, obj: Invoice) -> str:
        return f"{obj.student.first_name} {obj.student.last_name}".strip()

    def get_balance(self, obj: Invoice):
        return max(obj.total_amount - obj.paid_amount, 0)

    class Meta:
        model = Invoice
        fields = "__all__"
        read_only_fields = ("school",)


class PaymentSerializer(serializers.ModelSerializer):
    invoice_student_name = serializers.SerializerMethodField()

    def get_invoice_student_name(self, obj: Payment) -> str:
        return f"{obj.invoice.student.first_name} {obj.invoice.student.last_name}".strip()

    class Meta:
        model = Payment
        fields = "__all__"
        read_only_fields = ("school",)
