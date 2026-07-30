from datetime import date

from .models import AcademicYear


def get_or_create_default_academic_year(school) -> AcademicYear:
    """
    Return the school's active academic year, creating a sensible default if none exists.

    New schools start with no academic year, which would otherwise block creating
    grade levels (ClassLevel requires an academic year).
    """
    active = AcademicYear.objects.filter(school=school, is_active=True).first()
    if active:
        return active

    latest = AcademicYear.objects.filter(school=school).order_by("-start_date").first()
    if latest:
        return latest

    today = date.today()
    start_year = today.year if today.month >= 4 else today.year - 1
    start_date = date(start_year, 4, 1)
    end_date = date(start_year + 1, 3, 31)

    academic_year, _ = AcademicYear.objects.get_or_create(
        school=school,
        name=f"{start_year}-{start_year + 1}",
        defaults={
            "start_date": start_date,
            "end_date": end_date,
            "is_active": True,
        },
    )
    return academic_year
