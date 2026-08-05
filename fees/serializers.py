from decimal import Decimal

from django.db import transaction
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
    fund_name = serializers.CharField(source="fund.name", read_only=True, default="")
    tenure = serializers.CharField(source="fund.tenure", read_only=True, default="")
    balance = serializers.SerializerMethodField()

    def get_student_name(self, obj: Invoice) -> str:
        return f"{obj.student.first_name} {obj.student.last_name}".strip()

    def get_balance(self, obj: Invoice):
        return max(obj.total_amount - obj.paid_amount, 0)

    class Meta:
        model = Invoice
        fields = "__all__"
        read_only_fields = ("school",)

    def validate(self, attrs):
        invoice_type = attrs.get("invoice_type", getattr(self.instance, "invoice_type", Invoice.TYPE_MONTHLY_FEE))
        fund = attrs.get("fund", getattr(self.instance, "fund", None))
        fee_structure = attrs.get("fee_structure", getattr(self.instance, "fee_structure", None))
        student = attrs.get("student", getattr(self.instance, "student", None))

        if invoice_type == Invoice.TYPE_FUND:
            if fund is None:
                raise serializers.ValidationError({"fund": "Fund is required for fund invoices."})
            attrs["fee_structure"] = None
            if student is not None:
                existing = Invoice.objects.filter(
                    fund=fund, student=student, invoice_type=Invoice.TYPE_FUND
                )
                if self.instance is not None:
                    existing = existing.exclude(pk=self.instance.pk)
                if existing.exists():
                    raise serializers.ValidationError(
                        {
                            "student": (
                                "This student already has an invoice for this fund. "
                                "Use Record Payment on the existing invoice to collect."
                            )
                        }
                    )
            if "total_amount" not in attrs and self.instance is None:
                attrs["total_amount"] = fund.amount
            if "due_date" not in attrs and self.instance is None and fund.due_on:
                attrs["due_date"] = fund.due_on
        else:
            attrs["fund"] = None
            if fee_structure is None and self.instance is None:
                raise serializers.ValidationError(
                    {"fee_structure": "Class tuition is required for monthly fee invoices."}
                )
        return attrs


class PaymentSerializer(serializers.ModelSerializer):
    invoice_student_name = serializers.SerializerMethodField()

    def get_invoice_student_name(self, obj: Payment) -> str:
        return f"{obj.invoice.student.first_name} {obj.invoice.student.last_name}".strip()

    class Meta:
        model = Payment
        fields = "__all__"
        read_only_fields = ("school",)

    def validate_amount(self, value):
        if value is None or value <= 0:
            raise serializers.ValidationError("Payment amount must be greater than zero.")
        return value

    def validate(self, attrs):
        invoice = attrs.get("invoice", getattr(self.instance, "invoice", None))
        amount = attrs.get("amount")
        if invoice is not None and amount is not None and self.instance is None:
            remaining = invoice.total_amount - invoice.paid_amount
            if amount > remaining:
                raise serializers.ValidationError(
                    {"amount": f"Payment exceeds remaining balance of {remaining}."}
                )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        from funds.services import apply_payment_to_invoice

        invoice = validated_data["invoice"]
        amount = Decimal(str(validated_data["amount"]))
        payment = Payment.objects.create(**validated_data)
        apply_payment_to_invoice(invoice=invoice, amount=amount)
        return payment
