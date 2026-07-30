from django.db import migrations


def map_interested_classes(apps, schema_editor):
    Inquiry = apps.get_model("admissions", "Inquiry")
    ClassLevel = apps.get_model("academics", "ClassLevel")

    for inquiry in Inquiry.objects.filter(
        interested_class_level__isnull=True
    ).exclude(interested_class=""):
        class_level = ClassLevel.objects.filter(
            school_id=inquiry.school_id,
            name__iexact=inquiry.interested_class.strip(),
        ).first()
        if class_level is None:
            continue
        inquiry.interested_class_level_id = class_level.id
        # Keep legacy text for compatibility.
        inquiry.save(update_fields=["interested_class_level"])


def clear_duplicate_admission_students(apps, schema_editor):
    """Ensure OneToOne student links: keep the earliest admission per student."""
    Admission = apps.get_model("admissions", "Admission")
    seen = set()
    for admission in Admission.objects.exclude(student_id=None).order_by("id"):
        if admission.student_id in seen:
            admission.student_id = None
            admission.save(update_fields=["student_id"])
        else:
            seen.add(admission.student_id)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("admissions", "0002_family_and_enrollment_fields"),
        ("academics", "0005_classlevel_is_board_class"),
    ]

    operations = [
        migrations.RunPython(clear_duplicate_admission_students, noop_reverse),
        migrations.RunPython(map_interested_classes, noop_reverse),
    ]
