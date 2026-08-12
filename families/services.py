from __future__ import annotations

from django.db import transaction

from .models import Family


def _normalize_email(value: str | None) -> str:
    return (value or "").strip().lower()


@transaction.atomic
def generate_family_code(*, school_id: int) -> str:
    prefix = "FAM"
    qs = Family.objects.select_for_update().filter(school_id=school_id, family_code__startswith=f"{prefix}-")
    max_num = 0
    for code in qs.values_list("family_code", flat=True):
        try:
            max_num = max(max_num, int(str(code).split("-")[-1]))
        except Exception:
            continue
    return f"{prefix}-{max_num + 1:04d}"


@transaction.atomic
def resolve_family(*, school, family_code: str | None = None, parent_email: str | None = None) -> Family:
    email = _normalize_email(parent_email)
    if family_code:
        code = family_code.strip().upper()
        family = Family.objects.filter(school=school, family_code=code).first()
        if family:
            return family
    if email:
        family = Family.objects.filter(school=school, primary_contact_email=email).order_by("id").first()
        if family:
            return family
    code = generate_family_code(school_id=school.id)
    family = Family.objects.create(
        school=school,
        family_code=code,
        primary_contact_email=email,
    )
    return family


def link_student_to_family(*, student, family: Family) -> None:
    if student.family_id != family.id:
        student.family = family
        student.save(update_fields=["family"])
    changed = False
    if not family.primary_contact_email and student.parent_email:
        family.primary_contact_email = _normalize_email(student.parent_email)
        changed = True
    if not family.father_name and student.father_name:
        family.father_name = student.father_name
        changed = True
    if not family.mother_name and student.mother_name:
        family.mother_name = student.mother_name
        changed = True
    if not family.address and student.address:
        family.address = student.address
        changed = True
    if changed:
        family.save(update_fields=["primary_contact_email", "father_name", "mother_name", "address", "updated_at"])
