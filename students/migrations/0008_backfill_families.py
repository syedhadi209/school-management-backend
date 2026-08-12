from django.db import migrations


def backfill_families(apps, schema_editor):
    Student = apps.get_model("students", "Student")
    Family = apps.get_model("families", "Family")

    for student in Student.objects.exclude(parent_email="").order_by("school_id", "id"):
        email = (student.parent_email or "").strip().lower()
        if not email:
            continue
        family = Family.objects.filter(school_id=student.school_id, primary_contact_email=email).order_by("id").first()
        if family is None:
            count = Family.objects.filter(school_id=student.school_id, family_code__startswith="FAM-").count()
            family = Family.objects.create(
                school_id=student.school_id,
                family_code=f"FAM-{count + 1:04d}",
                primary_contact_email=email,
                father_name=student.father_name or "",
                mother_name=student.mother_name or "",
                address=student.address or "",
            )
        student.family_id = family.id
        student.save(update_fields=["family"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("families", "0001_initial"),
        ("students", "0007_student_family"),
    ]

    operations = [
        migrations.RunPython(backfill_families, noop),
    ]
