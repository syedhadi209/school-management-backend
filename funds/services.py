from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from rest_framework.exceptions import ValidationError

from fees.models import Invoice
from students.models import Student


def eligible_students_for_fund(fund):
    class_ids = list(fund.class_levels.values_list("id", flat=True))
    if not class_ids:
        return Student.objects.none()
    return Student.objects.filter(
        school_id=fund.school_id,
        status="active",
        section__class_level_id__in=class_ids,
    ).select_related("section", "section__class_level")


@transaction.atomic
def sync_fund_invoices(fund) -> dict[str, int]:
    """Create missing fund-typed invoices for eligible active students."""
    if fund.status != fund.STATUS_ACTIVE:
        raise ValidationError({"status": "Only active funds can sync invoices."})

    students = list(eligible_students_for_fund(fund))
    existing = set(
        Invoice.objects.filter(fund=fund, invoice_type=Invoice.TYPE_FUND).values_list(
            "student_id", flat=True
        )
    )
    to_create = []
    for student in students:
        if student.id in existing:
            continue
        to_create.append(
            Invoice(
                school=fund.school,
                student=student,
                invoice_type=Invoice.TYPE_FUND,
                fund=fund,
                fee_structure=None,
                total_amount=fund.amount,
                paid_amount=Decimal("0"),
                status="unpaid",
                due_date=fund.due_on,
            )
        )
    if to_create:
        Invoice.objects.bulk_create(to_create, ignore_conflicts=True)
    return {
        "eligible": len(students),
        "created": len(to_create),
        "existing": len(existing),
    }


@transaction.atomic
def ensure_student_fund_invoices(student) -> int:
    """Attach active fund invoices matching the student's current class."""
    if student is None or student.section_id is None or student.status != "active":
        return 0
    class_level_id = student.section.class_level_id
    from funds.models import Fund

    funds = Fund.objects.filter(
        school_id=student.school_id,
        status=Fund.STATUS_ACTIVE,
        class_levels__id=class_level_id,
    ).distinct()
    created = 0
    for fund in funds:
        _, was_created = Invoice.objects.get_or_create(
            fund=fund,
            student=student,
            defaults={
                "school": student.school,
                "invoice_type": Invoice.TYPE_FUND,
                "fee_structure": None,
                "total_amount": fund.amount,
                "paid_amount": Decimal("0"),
                "status": "unpaid",
                "due_date": fund.due_on,
            },
        )
        if was_created:
            created += 1
    return created


@transaction.atomic
def activate_fund(fund, *, user=None) -> dict[str, int]:
    fund.status = fund.STATUS_ACTIVE
    update_fields = ["status", "updated_at"]
    fund.save(update_fields=update_fields)
    return sync_fund_invoices(fund)


def fund_invoice_summary(fund) -> dict[str, int]:
    qs = Invoice.objects.filter(fund=fund, invoice_type=Invoice.TYPE_FUND)
    return {
        "invoices_total": qs.count(),
        "unpaid": qs.filter(status="unpaid").count(),
        "partial": qs.filter(status="partial").count(),
        "paid": qs.filter(status="paid").count(),
    }


@transaction.atomic
def apply_payment_to_invoice(*, invoice: Invoice, amount: Decimal) -> Invoice:
    """Lock invoice and apply payment amount to paid_amount/status."""
    invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
    if amount <= 0:
        raise ValidationError({"amount": "Payment amount must be greater than zero."})
    remaining = invoice.total_amount - invoice.paid_amount
    if amount > remaining:
        raise ValidationError(
            {"amount": f"Payment exceeds remaining balance of {remaining}."}
        )
    invoice.paid_amount = invoice.paid_amount + amount
    if invoice.paid_amount >= invoice.total_amount:
        invoice.status = "paid"
        invoice.paid_amount = invoice.total_amount
    elif invoice.paid_amount > 0:
        invoice.status = "partial"
    else:
        invoice.status = "unpaid"
    invoice.save(update_fields=["paid_amount", "status"])
    return invoice
