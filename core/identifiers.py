from django.db.models import QuerySet
from django.utils import timezone


def next_readable_id(
    queryset: QuerySet,
    *,
    field_name: str,
    prefix: str,
    school_id: int | None,
) -> str:
    """
    Build a readable unique ID like STU-2026-0001 or TCH-2026-0001.

    Sequence is scoped to the school + calendar year.
    """
    year = timezone.now().year
    pattern_prefix = f"{prefix}-{year}-"
    filters = {f"{field_name}__startswith": pattern_prefix}
    if school_id is not None:
        filters["school_id"] = school_id

    max_seq = 0
    for value in queryset.filter(**filters).values_list(field_name, flat=True):
        try:
            seq = int(str(value).rsplit("-", 1)[-1])
        except (TypeError, ValueError):
            continue
        if seq > max_seq:
            max_seq = seq

    return f"{prefix}-{year}-{max_seq + 1:04d}"
