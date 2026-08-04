from datetime import date
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from core.permissions import is_school_admin_or_manager
from students.models import Student
from timetable.models import TimetableEntry
from timetable.services import school_local_now

from .models import AttendanceRecord, AttendanceSession


VALID_RECORD_STATUSES = {
    AttendanceRecord.STATUS_PRESENT,
    AttendanceRecord.STATUS_ABSENT,
    AttendanceRecord.STATUS_LATE,
    AttendanceRecord.STATUS_LEAVE,
}


def session_summary(session: AttendanceSession) -> dict[str, int]:
    counts = {
        "present": 0,
        "absent": 0,
        "late": 0,
        "leave": 0,
        "total": 0,
    }
    # Prefer prefetched cache when available.
    records = list(session.records.all())
    for record in records:
        status = record.status if hasattr(record, "status") else record
        if status in counts:
            counts[status] += 1
        counts["total"] += 1
    return counts


def active_roster_qs(section):
    return Student.objects.filter(section=section, status="active", school_id=section.school_id).order_by(
        "roll_number", "first_name", "last_name"
    )


def take_attendance(
    *,
    user,
    school,
    timetable_entry_id: int,
    attendance_date: date,
    records: list[dict[str, Any]],
    notes: str = "",
) -> AttendanceSession:
    if school is None:
        raise ValidationError({"detail": "Active school required."})

    try:
        entry = TimetableEntry.objects.select_related(
            "section", "teacher", "subject", "academic_year"
        ).get(pk=timetable_entry_id, school=school)
    except TimetableEntry.DoesNotExist as exc:
        raise ValidationError({"timetable_entry": "Timetable entry not found for your school."}) from exc

    if entry.slot_type != TimetableEntry.SLOT_LECTURE:
        raise ValidationError({"timetable_entry": "Attendance can only be taken for lectures, not breaks."})
    if not entry.is_active:
        raise ValidationError({"timetable_entry": "This timetable entry is inactive."})
    if entry.teacher_id is None:
        raise ValidationError({"timetable_entry": "Lecture has no assigned teacher."})

    is_admin = is_school_admin_or_manager(user)
    teacher = getattr(user, "teacher_profile", None)
    if not is_admin:
        if teacher is None or entry.teacher_id != teacher.id:
            raise PermissionDenied("You can only take attendance for your own lectures.")
        local_now, _, _ = school_local_now(school)
        if attendance_date != local_now.date():
            raise ValidationError(
                {"date": "Teachers may only mark attendance for today's school-local date."}
            )

    if not records:
        raise ValidationError({"records": "At least one attendance record is required."})

    roster = list(active_roster_qs(entry.section))
    roster_ids = {student.id for student in roster}
    if not roster_ids:
        raise ValidationError({"records": "This section has no active students."})

    seen_student_ids: set[int] = set()
    normalized: list[dict[str, Any]] = []
    for index, row in enumerate(records):
        student_id = row.get("student")
        status = row.get("status")
        remarks = (row.get("remarks") or "").strip()
        if student_id is None:
            raise ValidationError({f"records[{index}].student": "Student is required."})
        try:
            student_id = int(student_id)
        except (TypeError, ValueError) as exc:
            raise ValidationError({f"records[{index}].student": "Invalid student id."}) from exc
        if student_id in seen_student_ids:
            raise ValidationError({f"records[{index}].student": "Duplicate student in payload."})
        seen_student_ids.add(student_id)
        if student_id not in roster_ids:
            raise ValidationError(
                {f"records[{index}].student": "Student is not an active member of this section."}
            )
        if status not in VALID_RECORD_STATUSES:
            raise ValidationError(
                {
                    f"records[{index}].status": (
                        f"Invalid status. Choose one of: {', '.join(sorted(VALID_RECORD_STATUSES))}."
                    )
                }
            )
        normalized.append({"student_id": student_id, "status": status, "remarks": remarks[:255]})

    missing = roster_ids - seen_student_ids
    if missing:
        raise ValidationError(
            {
                "records": (
                    f"Attendance payload must include every active student in the section. "
                    f"Missing {len(missing)} student(s)."
                )
            }
        )

    now = timezone.now()
    with transaction.atomic():
        session = (
            AttendanceSession.objects.select_for_update()
            .filter(timetable_entry=entry, date=attendance_date)
            .first()
        )
        if session is None:
            try:
                session = AttendanceSession.objects.create(
                    school=school,
                    academic_year=entry.academic_year,
                    timetable_entry=entry,
                    section=entry.section,
                    teacher=entry.teacher,
                    subject=entry.subject,
                    date=attendance_date,
                    day_of_week=entry.day_of_week,
                    start_time=entry.start_time,
                    end_time=entry.end_time,
                    status=AttendanceSession.STATUS_SUBMITTED,
                    taken_by=user,
                    taken_at=now,
                    notes=notes or "",
                )
            except IntegrityError:
                session = AttendanceSession.objects.select_for_update().get(
                    timetable_entry=entry, date=attendance_date
                )

        session.academic_year = entry.academic_year
        session.section = entry.section
        session.teacher = entry.teacher
        session.subject = entry.subject
        session.day_of_week = entry.day_of_week
        session.start_time = entry.start_time
        session.end_time = entry.end_time
        session.status = AttendanceSession.STATUS_SUBMITTED
        session.taken_by = user
        session.taken_at = now
        session.notes = notes or ""
        session.save()

        existing = {
            record.student_id: record
            for record in AttendanceRecord.objects.select_for_update().filter(session=session)
        }
        to_create: list[AttendanceRecord] = []
        to_update: list[AttendanceRecord] = []
        for row in normalized:
            record = existing.get(row["student_id"])
            if record is None:
                to_create.append(
                    AttendanceRecord(
                        school=school,
                        session=session,
                        student_id=row["student_id"],
                        status=row["status"],
                        remarks=row["remarks"],
                    )
                )
            else:
                record.status = row["status"]
                record.remarks = row["remarks"]
                to_update.append(record)

        if to_create:
            AttendanceRecord.objects.bulk_create(to_create, ignore_conflicts=False)
        if to_update:
            AttendanceRecord.objects.bulk_update(to_update, ["status", "remarks", "marked_at"])

        # Drop records for students no longer in the submitted set (should not happen after validation).
        AttendanceRecord.objects.filter(session=session).exclude(student_id__in=seen_student_ids).delete()

    return (
        AttendanceSession.objects.select_related(
            "section__class_level",
            "teacher__user",
            "subject",
            "timetable_entry",
            "taken_by",
            "academic_year",
        )
        .prefetch_related("records__student")
        .get(pk=session.pk)
    )


def summarize_sessions(queryset) -> dict[str, Any]:
    sessions = list(queryset)
    session_ids = [session.id for session in sessions]
    counts = {
        "sessions_count": len(sessions),
        "present": 0,
        "absent": 0,
        "late": 0,
        "leave": 0,
        "total_records": 0,
        "attendance_rate": 0.0,
    }
    if not session_ids:
        return counts

    for status in AttendanceRecord.objects.filter(session_id__in=session_ids).values_list("status", flat=True):
        if status in counts:
            counts[status] += 1
        counts["total_records"] += 1

    attended = counts["present"] + counts["late"]
    if counts["total_records"]:
        counts["attendance_rate"] = round((attended / counts["total_records"]) * 100, 2)
    return counts


def draft_payload_for_entry(*, entry: TimetableEntry, attendance_date: date, session: AttendanceSession | None):
    roster = active_roster_qs(entry.section)
    existing = {}
    if session is not None:
        existing = {
            record.student_id: record
            for record in session.records.select_related("student").all()
        }

    records = []
    for student in roster:
        record = existing.get(student.id)
        records.append(
            {
                "student": student.id,
                "student_name": f"{student.first_name} {student.last_name}".strip(),
                "roll_number": student.roll_number,
                "status": record.status if record else AttendanceRecord.STATUS_PRESENT,
                "remarks": record.remarks if record else "",
                "marked_at": record.marked_at if record else None,
            }
        )
    return {
        "session_id": session.id if session else None,
        "status": session.status if session else AttendanceSession.STATUS_DRAFT,
        "date": attendance_date.isoformat(),
        "timetable_entry": entry.id,
        "section": entry.section_id,
        "teacher": entry.teacher_id,
        "subject": entry.subject_id,
        "notes": session.notes if session else "",
        "records": records,
        "summary": session_summary(session) if session else {
            "present": 0,
            "absent": 0,
            "late": 0,
            "leave": 0,
            "total": len(records),
        },
    }
