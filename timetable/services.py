from __future__ import annotations

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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
        return f"{label} has {break_name} {time_range} on {day}"
    subject = entry.subject.name if entry.subject_id else "a lecture"
    teacher_name = ""
    if entry.teacher_id and entry.teacher.user_id:
        teacher_name = f"{entry.teacher.user.first_name} {entry.teacher.user.last_name}".strip()
        teacher_name = teacher_name or entry.teacher.user.email
    if teacher_name:
        return f"{teacher_name} is already teaching {label} ({subject}) {time_range} on {day}"
    return f"{label} already has {subject} {time_range} on {day}"


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
