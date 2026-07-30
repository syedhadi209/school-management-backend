from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from academics.models import Section
from accounts.parent_services import provision_parent_for_student
from students.models import Student

from .models import Admission, Inquiry


def _split_name(inquiry: Inquiry) -> tuple[str, str]:
    first = (inquiry.first_name or "").strip()
    last = (inquiry.last_name or "").strip()
    if first or last:
        return first or inquiry.full_name.split()[0], last
    parts = inquiry.full_name.strip().split(None, 1)
    return parts[0], (parts[1] if len(parts) > 1 else "")


@transaction.atomic
def admit_and_enrol(
    *,
    inquiry: Inquiry,
    section: Section,
    acting_user,
    admission_date=None,
    student_status: str = "active",
) -> tuple[Student, Admission, bool]:
    """
    Convert an applied inquiry into a student + admission record.

    Returns (student, admission, created) where created is False when the
    inquiry was already admitted (idempotent re-submit).
    """
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

    if locked.status != "applied":
        raise ValidationError(
            {"detail": "Only inquiries in the Applied stage can be admitted. Move the inquiry to Applied first."}
        )

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
    student = Student.objects.create(
        school=locked.school,
        section=section,
        first_name=first_name,
        last_name=last_name,
        gender=locked.gender,
        date_of_birth=locked.date_of_birth,
        guardian_phone=locked.parent_phone or locked.phone,
        parent_alternate_phone=locked.parent_alternate_phone,
        parent_email=locked.parent_email,
        father_name=locked.father_name,
        mother_name=locked.mother_name,
        father_cnic=locked.father_cnic,
        mother_cnic=locked.mother_cnic,
        address=locked.address,
        region=locked.region,
        admission_date=admission_date or timezone.localdate(),
        status=student_status or "active",
    )

    if student.parent_email:
        provision_parent_for_student(
            student=student,
            email=student.parent_email,
            school=locked.school,
            relation="guardian",
            first_name=locked.father_name or locked.mother_name or "",
        )

    admission, _ = Admission.objects.get_or_create(
        inquiry=locked,
        defaults={"school": locked.school, "decision": "pending"},
    )
    if admission.school_id != locked.school_id:
        raise ValidationError({"detail": "Admission record belongs to a different school."})

    admission.mark_admitted(user=acting_user, student=student)

    locked.status = "admitted"
    locked.save(update_fields=["status", "updated_at"])

    return student, admission, True
