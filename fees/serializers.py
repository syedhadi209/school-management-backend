from rest_framework import serializers

from .models import FeeStructure, Invoice, Payment


class FeeStructureSerializer(serializers.ModelSerializer):
    class_level_name = serializers.CharField(source="class_level.name", read_only=True, default="")

    class Meta:
        model = FeeStructure
        fields = "__all__"
        read_only_fields = ("school",)


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

