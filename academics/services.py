from .models import ClassLevel, Section

DEFAULT_SECTION_NAME = "A"


def get_or_create_default_section(class_level: ClassLevel) -> Section:
    """
    Ensure a class has at least one section.

    Students are assigned to sections, not classes, so a class without any
    section is invisible in student and enrolment pickers.
    """
    existing = Section.objects.filter(class_level=class_level).order_by("name").first()
    if existing:
        return existing

    section, _ = Section.objects.get_or_create(
        class_level=class_level,
        name=DEFAULT_SECTION_NAME,
        defaults={"school_id": class_level.school_id},
    )
    return section
