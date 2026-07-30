"""
Parent portal account provisioning.

Creates or reuses a parent User + ParentProfile for a given email and links
them to a student. The invite email that lets a parent set their password is
deferred — accounts are created with an unusable password until that lands.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework.exceptions import ValidationError

from accounts.models import ParentProfile, RoleChoices, UserRole
from students.models import ParentStudentLink, Student

User = get_user_model()


def send_parent_invite(_parent: ParentProfile) -> None:
    """
    Deferred: email the parent a set-password / invite link.

    Hook this up once outbound email is configured. Until then parents cannot
    log in because accounts are created with set_unusable_password().
    """
    return None


def provision_parent_for_student(
    *,
    student: Student,
    email: str | None,
    school,
    relation: str = "guardian",
    first_name: str = "",
    last_name: str = "",
) -> ParentProfile | None:
    """
    Find or create a parent account for ``email`` and link it to ``student``.

    Returns the ParentProfile, or None when no email was provided.
    Raises ValidationError when the email belongs to a parent at another school.
    """
    cleaned = (email or "").strip().lower()
    if not cleaned:
        return None

    user = User.objects.filter(email__iexact=cleaned).first()
    if user is None:
        user = User(email=cleaned, username=cleaned, active_school=school)
        if first_name:
            user.first_name = first_name
        if last_name:
            user.last_name = last_name
        user.set_unusable_password()
        user.save()
    else:
        # Keep the name helpful when the account was created blank.
        updates = []
        if first_name and not user.first_name:
            user.first_name = first_name
            updates.append("first_name")
        if last_name and not user.last_name:
            user.last_name = last_name
            updates.append("last_name")
        if user.active_school_id is None:
            user.active_school = school
            updates.append("active_school")
        if updates:
            user.save(update_fields=updates)

    existing_profile = ParentProfile.objects.filter(user=user).select_related("school").first()
    if existing_profile is not None and existing_profile.school_id != school.id:
        raise ValidationError(
            {
                "parent_email": (
                    f"This email already belongs to a parent at another school "
                    f"({existing_profile.school.name}). Use a different email."
                )
            }
        )

    parent, _ = ParentProfile.objects.get_or_create(user=user, defaults={"school": school})
    UserRole.objects.get_or_create(user=user, school=school, role=RoleChoices.PARENT)
    ParentStudentLink.objects.get_or_create(
        parent=parent,
        student=student,
        defaults={"school": school, "relation": relation or "guardian"},
    )
    return parent
