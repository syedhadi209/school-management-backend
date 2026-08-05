from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from rest_framework.exceptions import ValidationError

from .models import FeeStructure, StudentMonthlyFee


def get_class_monthly_fee(*, school, class_level) -> FeeStructure | None:
    if school is None or class_level is None:
        return None
    return FeeStructure.objects.filter(school=school, class_level=class_level).first()


@transaction.atomic
def upsert_student_monthly_fee(
    *,
    student,
    discount_amount: Decimal | None = None,
    notes: str | None = None,
    refresh_base: bool = True,
) -> StudentMonthlyFee | None:
    """
    Create or update the student's monthly fee from their section's class fee.

    If the student has no section or the class has no FeeStructure, delete any
    existing monthly fee row and return None.
    """
    section = student.section
    if section is None:
        StudentMonthlyFee.objects.filter(student=student).delete()
        return None

    structure = get_class_monthly_fee(school=student.school, class_level=section.class_level)
    if structure is None:
        StudentMonthlyFee.objects.filter(student=student).delete()
        return None

    existing = StudentMonthlyFee.objects.filter(student=student).first()
    base = structure.amount if refresh_base or existing is None else existing.base_amount
    discount = (
        Decimal(discount_amount)
        if discount_amount is not None
        else (existing.discount_amount if existing else Decimal("0"))
    )
    if discount < 0:
        raise ValidationError({"discount_amount": "Discount cannot be negative."})
    if discount > base:
        raise ValidationError({"discount_amount": "Discount cannot exceed the class monthly fee."})

    fee_notes = notes if notes is not None else (existing.notes if existing else "")

    fee, _ = StudentMonthlyFee.objects.update_or_create(
        student=student,
        defaults={
            "school": student.school,
            "fee_structure": structure,
            "base_amount": base,
            "discount_amount": discount,
            "notes": fee_notes or "",
        },
    )
    return fee
