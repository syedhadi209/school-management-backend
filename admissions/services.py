from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from academics.models import Section
from accounts.parent_services import provision_parent_for_student
from families.services import link_student_to_family, resolve_family
from fees.services import upsert_student_monthly_fee
from funds.services import ensure_student_fund_invoices
from students.models import Student

from .models import Admission, Inquiry


def _split_name(inquiry: Inquiry) -> tuple[str, str]:
    first = (inquiry.first_name or "").strip()
    last = (inquiry.last_name or "").strip()
    if first or last:
        return first or inquiry.full_name.split()[0], last
    parts = inquiry.full_name.strip().split(None, 1)
    return parts[0], (parts[1] if len(parts) > 1 else "")


def _coalesce(payload: dict, inquiry: Inquiry, key: str, fallback=None):
    value = payload.get(key, None)
    if value not in (None, ""):
        return value
    src = getattr(inquiry, key, None)
    if src not in (None, ""):
        return src
    return fallback


@transaction.atomic
def admit_and_enrol(
    *,
    inquiry: Inquiry,
    section: Section,
    acting_user,
    admission_date=None,
    student_status: str = "active",
    student_payload: dict | None = None,
) -> tuple[Student, Admission, bool]:
    """
    Convert an inquiry into a student + admission record.

    Returns (student, admission, created) where created is False when the
    inquiry was already admitted (idempotent re-submit).
    """
    payload = student_payload or {}
    locked = Inquiry.objects.select_for_update().get(pk=inquiry.pk)

    if locked.status == "admitted":
        try:
            admission = locked.admission
        except Admission.DoesNotExist as exc:
            raise ValidationError({"detail": "Inquiry is marked admitted but has no admission record."}) from exc
        if admission.student_id is None:
            raise ValidationError({"detail": "Inquiry is marked admitted but has no linked student."})
        return admission.student, admission, False

    if locked.status == "rejected":
        raise ValidationError({"detail": "Rejected inquiries cannot be admitted."})

    allowed = {"new", "contacted", "visited", "applied"}
    if locked.status not in allowed:
        raise ValidationError({"detail": "Inquiry is not eligible for admission."})

    if section.school_id != locked.school_id:
        raise ValidationError({"section": "Section must belong to the same school as the inquiry."})

    enrolled_count = Student.objects.filter(section=section, status="active").count()
    if enrolled_count >= section.capacity:
        raise ValidationError(
            {
                "section": (
                    f"{section.class_level.name} - {section.name} is at capacity "
                    f"({section.capacity} students)."
                )
            }
        )

    first_name, last_name = _split_name(locked)
    first_name = _coalesce(payload, locked, "first_name", first_name).strip()
    last_name = _coalesce(payload, locked, "last_name", last_name).strip()

    student = Student.objects.create(
        school=locked.school,
        section=section,
        first_name=first_name,
        last_name=last_name,
        gender=_coalesce(payload, locked, "gender", ""),
        date_of_birth=_coalesce(payload, locked, "date_of_birth"),
        guardian_phone=_coalesce(payload, locked, "guardian_phone", locked.parent_phone or locked.phone or ""),
        parent_alternate_phone=_coalesce(payload, locked, "parent_alternate_phone", ""),
        parent_email=_coalesce(payload, locked, "parent_email", ""),
        parent_occupation=_coalesce(payload, locked, "parent_occupation", ""),
        father_name=_coalesce(payload, locked, "father_name", ""),
        mother_name=_coalesce(payload, locked, "mother_name", ""),
        father_cnic=_coalesce(payload, locked, "father_cnic", ""),
        mother_cnic=_coalesce(payload, locked, "mother_cnic", ""),
        address=_coalesce(payload, locked, "address", ""),
        region=_coalesce(payload, locked, "region", ""),
        board_roll_number=_coalesce(payload, locked, "board_roll_number", ""),
        admission_date=admission_date or timezone.localdate(),
        status=student_status or "active",
        profile_image=payload.get("profile_image") or None,
    )

    if student.parent_email:
        provision_parent_for_student(
            student=student,
            email=student.parent_email,
            school=locked.school,
            relation="guardian",
            first_name=student.father_name or student.mother_name or "",
        )

    # Keep inquiry data in sync with final enrolment payload.
    for field in [
        "first_name",
        "last_name",
        "gender",
        "date_of_birth",
        "father_name",
        "mother_name",
        "father_cnic",
        "mother_cnic",
        "address",
        "region",
        "parent_email",
        "parent_phone",
        "parent_alternate_phone",
        "parent_occupation",
        "board_roll_number",
        "family_lookup_code",
    ]:
        if field in payload and payload[field] not in (None, ""):
            setattr(locked, field, payload[field])

    if student.section_id is not None:
        discount_amount = payload.get("discount_amount", None)
        fee_notes = (payload.get("fee_notes") or "").strip()
        if discount_amount is None:
            upsert_student_monthly_fee(student=student, refresh_base=True)
        else:
            upsert_student_monthly_fee(
                student=student,
                discount_amount=Decimal(str(discount_amount)),
                notes=fee_notes,
                refresh_base=True,
            )
        ensure_student_fund_invoices(student)

    family = resolve_family(
        school=student.school,
        family_code=(payload.get("family_lookup_code") or "").strip().upper() or None,
        parent_email=student.parent_email or None,
    )
    link_student_to_family(student=student, family=family)

    admission, _ = Admission.objects.get_or_create(
        inquiry=locked,
        defaults={"school": locked.school, "decision": "pending"},
    )
    if admission.school_id != locked.school_id:
        raise ValidationError({"detail": "Admission record belongs to a different school."})

    admission.mark_admitted(user=acting_user, student=student)

    locked.status = "admitted"
    locked.full_name = f"{student.first_name} {student.last_name}".strip() or locked.full_name
    locked.save()

    return student, admission, True
