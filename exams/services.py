from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from academics.models import TeacherSubjectAssignment
from core.permissions import is_school_admin_or_manager, is_teacher_only
from schools.services import get_or_create_default_academic_year
from students.models import Student
from timetable.services import section_label

from .models import Exam, Mark, MarkSheet


def active_roster_qs(section):
    return Student.objects.filter(
        section=section, status="active", school_id=section.school_id
    ).order_by("roll_number", "first_name", "last_name")


def teacher_can_teach(teacher, section, subject, academic_year) -> bool:
    if teacher is None or section is None or subject is None or academic_year is None:
        return False
    return TeacherSubjectAssignment.objects.filter(
        school_id=section.school_id,
        teacher=teacher,
        section=section,
        subject=subject,
        academic_year=academic_year,
    ).exists()


def teacher_assignment_pairs(teacher, academic_year):
    return list(
        TeacherSubjectAssignment.objects.filter(
            teacher=teacher, academic_year=academic_year
        ).values_list("section_id", "subject_id")
    )


def sheet_summary(sheet: MarkSheet) -> dict[str, Any]:
    marks = list(sheet.marks.all())
    total = len(marks)
    if total == 0:
        return {
            "count": 0,
            "average": None,
            "average_percentage": None,
        }
    obtained = sum((m.marks_obtained for m in marks), Decimal("0"))
    max_total = sum((m.max_marks for m in marks), Decimal("0"))
    average = (obtained / total).quantize(Decimal("0.01"))
    avg_pct = None
    if max_total > 0:
        avg_pct = float((obtained / max_total * 100).quantize(Decimal("0.01")))
    return {
        "count": total,
        "average": float(average),
        "average_percentage": avg_pct,
    }


def sheet_completion_summary(exam: Exam) -> dict[str, int]:
    sheets = exam.mark_sheets.all()
    submitted = sheets.filter(status=MarkSheet.STATUS_SUBMITTED).count()
    draft = sheets.filter(status=MarkSheet.STATUS_DRAFT).count()
    return {
        "sheets_total": sheets.count(),
        "sheets_submitted": submitted,
        "sheets_draft": draft,
    }


@transaction.atomic
def create_class_test(
    *,
    user,
    school,
    name: str,
    section,
    subject,
    max_marks: Decimal | None = None,
    starts_on=None,
    ends_on=None,
    academic_year=None,
) -> Exam:
    if school is None:
        raise ValidationError({"detail": "Active school required."})
    teacher = getattr(user, "teacher_profile", None)
    if teacher is None and not is_school_admin_or_manager(user):
        raise PermissionDenied("Teacher profile required.")

    academic_year = academic_year or get_or_create_default_academic_year(school)
    if section.school_id != school.id:
        raise ValidationError({"section": "Section must belong to your school."})
    if subject.school_id != school.id:
        raise ValidationError({"subject": "Subject must belong to your school."})

    if is_teacher_only(user):
        if teacher is None or not teacher_can_teach(teacher, section, subject, academic_year):
            raise PermissionDenied(
                "You can only create class tests for sections and subjects you are assigned to teach."
            )

    max_marks = Decimal(max_marks if max_marks is not None else 100)
    if max_marks <= 0:
        raise ValidationError({"max_marks": "Max marks must be greater than zero."})

    name = (name or "").strip()
    if not name:
        raise ValidationError({"name": "Exam name is required."})

    if Exam.objects.filter(
        academic_year=academic_year,
        section=section,
        subject=subject,
        name=name,
        exam_type=Exam.TYPE_CLASS_TEST,
    ).exists():
        raise ValidationError({"name": "A class test with this name already exists for this section and subject."})

    exam = Exam.objects.create(
        school=school,
        academic_year=academic_year,
        name=name,
        exam_type=Exam.TYPE_CLASS_TEST,
        status=Exam.STATUS_OPEN,
        section=section,
        subject=subject,
        max_marks=max_marks,
        starts_on=starts_on,
        ends_on=ends_on or starts_on,
        created_by=user,
    )
    MarkSheet.objects.create(
        school=school,
        academic_year=academic_year,
        exam=exam,
        section=section,
        subject=subject,
        teacher=teacher,
        status=MarkSheet.STATUS_DRAFT,
        max_marks=max_marks,
    )
    return exam


@transaction.atomic
def create_term_exam(
    *,
    user,
    school,
    name: str,
    exam_type: str,
    max_marks: Decimal | None = None,
    starts_on=None,
    ends_on=None,
    academic_year=None,
) -> Exam:
    if not is_school_admin_or_manager(user):
        raise PermissionDenied("Only school admins and managers can create midterms and finals.")
    if school is None:
        raise ValidationError({"detail": "Active school required."})
    if exam_type not in {Exam.TYPE_MIDTERM, Exam.TYPE_FINAL}:
        raise ValidationError({"exam_type": "exam_type must be midterm or final."})

    academic_year = academic_year or get_or_create_default_academic_year(school)
    name = (name or "").strip()
    if not name:
        raise ValidationError({"name": "Exam name is required."})
    max_marks = Decimal(max_marks if max_marks is not None else 100)
    if max_marks <= 0:
        raise ValidationError({"max_marks": "Max marks must be greater than zero."})

    if Exam.objects.filter(
        school=school, academic_year=academic_year, name=name, exam_type__in=[Exam.TYPE_MIDTERM, Exam.TYPE_FINAL]
    ).exists():
        raise ValidationError({"name": "An exam with this name already exists for this year."})

    return Exam.objects.create(
        school=school,
        academic_year=academic_year,
        name=name,
        exam_type=exam_type,
        status=Exam.STATUS_OPEN,
        section=None,
        subject=None,
        max_marks=max_marks,
        starts_on=starts_on,
        ends_on=ends_on,
        created_by=user,
    )


def get_or_create_sheet(*, exam: Exam, section, subject, teacher=None) -> MarkSheet:
    sheet, created = MarkSheet.objects.get_or_create(
        exam=exam,
        section=section,
        subject=subject,
        defaults={
            "school": exam.school,
            "academic_year": exam.academic_year,
            "teacher": teacher,
            "status": MarkSheet.STATUS_DRAFT,
            "max_marks": exam.max_marks,
        },
    )
    if not created and teacher is not None and sheet.teacher_id is None:
        sheet.teacher = teacher
        sheet.save(update_fields=["teacher", "updated_at"])
    return sheet


def draft_sheet(*, user, school, exam_id: int, section_id: int, subject_id: int) -> dict[str, Any]:
    if school is None:
        raise ValidationError({"detail": "Active school required."})
    try:
        exam = Exam.objects.select_related("section", "subject", "academic_year").get(
            pk=exam_id, school=school
        )
    except Exam.DoesNotExist as exc:
        raise ValidationError({"exam": "Exam not found."}) from exc

    if exam.status == Exam.STATUS_PUBLISHED:
        raise ValidationError({"exam": "This exam is published. Unpublish it before editing marks."})

    from academics.models import Section, Subject

    try:
        section = Section.objects.get(pk=section_id, school=school)
        subject = Subject.objects.get(pk=subject_id, school=school)
    except (Section.DoesNotExist, Subject.DoesNotExist) as exc:
        raise ValidationError({"detail": "Section or subject not found."}) from exc

    if exam.exam_type == Exam.TYPE_CLASS_TEST:
        if exam.section_id != section.id or exam.subject_id != subject.id:
            raise ValidationError(
                {"detail": "Class tests are locked to their section and subject."}
            )

    teacher = getattr(user, "teacher_profile", None)
    is_admin = is_school_admin_or_manager(user)
    if not is_admin:
        if teacher is None or not teacher_can_teach(teacher, section, subject, exam.academic_year):
            raise PermissionDenied("You are not assigned to teach this section and subject.")

    sheet = get_or_create_sheet(exam=exam, section=section, subject=subject, teacher=teacher)
    existing = {
        mark.student_id: mark
        for mark in Mark.objects.filter(exam=exam, subject=subject, student__section=section).select_related(
            "student"
        )
    }
    roster = list(active_roster_qs(section))
    records = []
    for student in roster:
        mark = existing.get(student.id)
        records.append(
            {
                "student": student.id,
                "student_name": f"{student.first_name} {student.last_name}".strip(),
                "roll_number": student.roll_number or "",
                "marks_obtained": float(mark.marks_obtained) if mark else None,
                "remarks": mark.remarks if mark else "",
            }
        )

    return {
        "sheet_id": sheet.id,
        "exam": exam.id,
        "exam_name": exam.name,
        "exam_type": exam.exam_type,
        "exam_status": exam.status,
        "section": section.id,
        "section_label": section_label(section),
        "subject": subject.id,
        "subject_name": subject.name,
        "status": sheet.status,
        "max_marks": float(sheet.max_marks),
        "notes": sheet.notes,
        "records": records,
        "summary": sheet_summary(sheet) if sheet.status == MarkSheet.STATUS_SUBMITTED else {
            "count": len([r for r in records if r["marks_obtained"] is not None]),
            "average": None,
            "average_percentage": None,
        },
    }


@transaction.atomic
def enter_marks(
    *,
    user,
    school,
    exam_id: int,
    section_id: int,
    subject_id: int,
    records: list[dict[str, Any]],
    max_marks: Decimal | None = None,
    notes: str = "",
) -> MarkSheet:
    if school is None:
        raise ValidationError({"detail": "Active school required."})

    try:
        exam = Exam.objects.select_related("academic_year", "section", "subject").get(
            pk=exam_id, school=school
        )
    except Exam.DoesNotExist as exc:
        raise ValidationError({"exam": "Exam not found."}) from exc

    if exam.status == Exam.STATUS_PUBLISHED:
        raise ValidationError({"exam": "Published exams are locked. Ask an admin to unpublish first."})

    from academics.models import Section, Subject

    try:
        section = Section.objects.select_related("class_level").get(pk=section_id, school=school)
        subject = Subject.objects.get(pk=subject_id, school=school)
    except (Section.DoesNotExist, Subject.DoesNotExist) as exc:
        raise ValidationError({"detail": "Section or subject not found."}) from exc

    if exam.exam_type == Exam.TYPE_CLASS_TEST:
        if exam.section_id != section.id or exam.subject_id != subject.id:
            raise ValidationError({"detail": "Class tests are locked to their section and subject."})

    teacher = getattr(user, "teacher_profile", None)
    is_admin = is_school_admin_or_manager(user)
    if not is_admin:
        if teacher is None or not teacher_can_teach(teacher, section, subject, exam.academic_year):
            raise PermissionDenied("You are not assigned to teach this section and subject.")

    roster = list(active_roster_qs(section))
    roster_ids = {student.id for student in roster}
    if not roster_ids:
        raise ValidationError({"records": "This section has no active students."})

    sheet_max = Decimal(max_marks if max_marks is not None else (exam.max_marks or 100))
    if sheet_max <= 0:
        raise ValidationError({"max_marks": "Max marks must be greater than zero."})

    if not records:
        raise ValidationError({"records": "At least one mark record is required."})

    seen: set[int] = set()
    normalized: list[dict[str, Any]] = []
    for index, row in enumerate(records):
        student_id = row.get("student")
        if student_id is None:
            raise ValidationError({f"records[{index}].student": "Student is required."})
        student_id = int(student_id)
        if student_id in seen:
            raise ValidationError({f"records[{index}].student": "Duplicate student in payload."})
        seen.add(student_id)
        if student_id not in roster_ids:
            raise ValidationError(
                {f"records[{index}].student": "Student is not an active member of this section."}
            )
        raw_marks = row.get("marks_obtained")
        if raw_marks is None or raw_marks == "":
            raise ValidationError({f"records[{index}].marks_obtained": "Marks are required for every student."})
        try:
            obtained = Decimal(str(raw_marks))
        except Exception as exc:
            raise ValidationError({f"records[{index}].marks_obtained": "Enter a valid number."}) from exc
        if obtained < 0 or obtained > sheet_max:
            raise ValidationError(
                {
                    f"records[{index}].marks_obtained": f"Marks must be between 0 and {sheet_max}."
                }
            )
        normalized.append(
            {
                "student": student_id,
                "marks_obtained": obtained,
                "remarks": (row.get("remarks") or "").strip()[:255],
            }
        )

    if seen != roster_ids:
        missing = roster_ids - seen
        raise ValidationError(
            {
                "records": (
                    f"Submit marks for every active student. "
                    f"Missing {len(missing)} student{'s' if len(missing) != 1 else ''}."
                )
            }
        )

    sheet = get_or_create_sheet(exam=exam, section=section, subject=subject, teacher=teacher)
    sheet.max_marks = sheet_max
    sheet.notes = (notes or "").strip()
    sheet.status = MarkSheet.STATUS_SUBMITTED
    sheet.submitted_at = timezone.now()
    sheet.submitted_by = user
    if teacher is not None:
        sheet.teacher = teacher
    sheet.save()

    for row in normalized:
        Mark.objects.update_or_create(
            exam=exam,
            student_id=row["student"],
            subject=subject,
            defaults={
                "school": school,
                "sheet": sheet,
                "teacher": teacher,
                "marks_obtained": row["marks_obtained"],
                "max_marks": sheet_max,
                "remarks": row["remarks"],
            },
        )

    if exam.status == Exam.STATUS_DRAFT:
        exam.status = Exam.STATUS_OPEN
        exam.save(update_fields=["status", "updated_at"])

    return (
        MarkSheet.objects.select_related(
            "exam", "section__class_level", "subject", "teacher__user", "submitted_by"
        )
        .prefetch_related("marks__student")
        .get(pk=sheet.pk)
    )


@transaction.atomic
def publish_exam(*, user, exam: Exam) -> Exam:
    is_admin = is_school_admin_or_manager(user)

    if exam.exam_type == Exam.TYPE_CLASS_TEST:
        if not is_admin:
            teacher = getattr(user, "teacher_profile", None)
            if teacher is None:
                raise PermissionDenied("Teacher profile required.")
            owns = exam.created_by_id == user.id or exam.mark_sheets.filter(teacher=teacher).exists()
            if not owns:
                raise PermissionDenied("You can only publish class tests you created or marked.")
    else:
        if not is_admin:
            raise PermissionDenied("Only school admins and managers can publish midterms and finals.")

    submitted = exam.mark_sheets.filter(status=MarkSheet.STATUS_SUBMITTED).exists()
    if not submitted and not exam.marks.exists():
        raise ValidationError({"detail": "Enter and submit marks before publishing."})

    exam.status = Exam.STATUS_PUBLISHED
    exam.published_at = timezone.now()
    exam.published_by = user
    exam.save(update_fields=["status", "published_at", "published_by", "updated_at"])
    return exam


@transaction.atomic
def unpublish_exam(*, user, exam: Exam) -> Exam:
    if not is_school_admin_or_manager(user):
        raise PermissionDenied("Only school admins and managers can unpublish exams.")
    exam.status = Exam.STATUS_OPEN
    exam.published_at = None
    exam.published_by = None
    exam.save(update_fields=["status", "published_at", "published_by", "updated_at"])
    return exam
