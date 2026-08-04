from __future__ import annotations

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.db.models import Q
from django.utils import timezone

from .models import TimetableEntry


DAY_LABELS = dict(TimetableEntry.DAY_CHOICES)


def section_label(section) -> str:
    class_name = getattr(getattr(section, "class_level", None), "name", "") or ""
    section_name = getattr(section, "name", "") or ""
    if class_name and section_name:
        return f"{class_name}-{section_name}"
    return class_name or section_name or "Section"


def format_time(value) -> str:
    if value is None:
        return ""
    return value.strftime("%H:%M")


def describe_entry(entry: TimetableEntry) -> str:
    day = DAY_LABELS.get(entry.day_of_week, str(entry.day_of_week))
    time_range = f"{format_time(entry.start_time)}–{format_time(entry.end_time)}"
    label = section_label(entry.section)
    if entry.slot_type == TimetableEntry.SLOT_BREAK:
        break_name = entry.label or "Break"
        return f"{label} already has {break_name} on {day} ({time_range})"
    subject = entry.subject.name if entry.subject_id else "a lecture"
    teacher_name = ""
    if entry.teacher_id and entry.teacher.user_id:
        teacher_name = f"{entry.teacher.user.first_name} {entry.teacher.user.last_name}".strip()
        teacher_name = teacher_name or entry.teacher.user.email
    if teacher_name:
        return f"{teacher_name} already teaches {subject} for {label} on {day} ({time_range})"
    return f"{label} already has {subject} on {day} ({time_range})"


def describe_teacher_conflict(entry: TimetableEntry) -> str:
    """Actionable message when a teacher is already booked in this window."""
    return (
        f"This teacher is busy: {describe_entry(entry)}. "
        "Pick another teacher, or free them from that slot first."
    )


def describe_section_conflict(entry: TimetableEntry) -> str:
    """Actionable message when a section already has a slot in this window."""
    return (
        f"This class already has a slot then: {describe_entry(entry)}. "
        "Choose a different time, or edit the existing slot."
    )


def describe_same_slot_conflict(entry: TimetableEntry) -> str:
    """Single message when the clash is both the same section and the same teacher."""
    return (
        f"That time is already taken: {describe_entry(entry)}. "
        "Choose a different time, or edit the existing slot."
    )


def overlapping_entries(
    *,
    school,
    academic_year,
    day_of_week: int,
    start_time,
    end_time,
    section=None,
    teacher=None,
    exclude_id: int | None = None,
):
    """Return active entries that overlap the given time window for section and/or teacher."""
    base = TimetableEntry.objects.filter(
        school=school,
        academic_year=academic_year,
        day_of_week=day_of_week,
        is_active=True,
        start_time__lt=end_time,
        end_time__gt=start_time,
    ).select_related("section__class_level", "subject", "teacher__user")
    if exclude_id:
        base = base.exclude(pk=exclude_id)

    results = []
    if section is not None:
        clash = base.filter(section=section).first()
        if clash is not None:
            results.append(clash)
    if teacher is not None:
        clash = base.filter(teacher=teacher).first()
        if clash is not None and (not results or results[0].pk != clash.pk):
            results.append(clash)
    return results


def find_section_overlap(
    *,
    school,
    academic_year,
    day_of_week: int,
    start_time,
    end_time,
    section,
    exclude_id: int | None = None,
):
    qs = TimetableEntry.objects.filter(
        school=school,
        academic_year=academic_year,
        section=section,
        day_of_week=day_of_week,
        is_active=True,
        start_time__lt=end_time,
        end_time__gt=start_time,
    ).select_related("section__class_level", "subject", "teacher__user")
    if exclude_id:
        qs = qs.exclude(pk=exclude_id)
    return qs.first()


def find_teacher_overlap(
    *,
    school,
    academic_year,
    day_of_week: int,
    start_time,
    end_time,
    teacher,
    exclude_id: int | None = None,
):
    """Return another active lecture where this teacher is already assigned."""
    qs = TimetableEntry.objects.filter(
        school=school,
        academic_year=academic_year,
        teacher=teacher,
        day_of_week=day_of_week,
        is_active=True,
        start_time__lt=end_time,
        end_time__gt=start_time,
    ).select_related("section__class_level", "subject", "teacher__user")
    if exclude_id:
        qs = qs.exclude(pk=exclude_id)
    return qs.first()


def school_local_now(school):
    """Return school-local datetime, weekday (0=Mon), and local time."""
    tz_name = getattr(school, "timezone", None) or "Asia/Karachi"
    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        tz = ZoneInfo("Asia/Karachi")
    now = timezone.now().astimezone(tz)
    # Python weekday: Monday=0 … Sunday=6 — matches TimetableEntry.DAY_* constants.
    return now, now.weekday(), now.time().replace(microsecond=0)


def teacher_schedule_q(teacher, school) -> Q:
    """
    Lectures assigned to the teacher, plus breaks only on days/sections they teach
    (and class-teacher sections). Avoids flooding the portal with identical
    recess/lunch cards from every M2M section roster.
    """
    from academics.models import Section

    from .models import TimetableEntry

    lecture_rows = list(
        TimetableEntry.objects.filter(
            school=school,
            teacher=teacher,
            slot_type=TimetableEntry.SLOT_LECTURE,
            is_active=True,
        ).values_list("day_of_week", "section_id")
    )
    break_q = Q(pk__in=[])  # empty
    sections_by_day: dict[int, set[int]] = {}
    for day_of_week, section_id in lecture_rows:
        sections_by_day.setdefault(day_of_week, set()).add(section_id)
    for day_of_week, section_ids in sections_by_day.items():
        break_q |= Q(
            slot_type=TimetableEntry.SLOT_BREAK,
            day_of_week=day_of_week,
            section_id__in=section_ids,
        )

    class_teacher_ids = list(
        Section.objects.filter(school=school, class_teacher=teacher).values_list("id", flat=True)
    )
    if class_teacher_ids:
        break_q |= Q(slot_type=TimetableEntry.SLOT_BREAK, section_id__in=class_teacher_ids)

    return Q(teacher=teacher) | break_q

