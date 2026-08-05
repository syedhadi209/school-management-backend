# Generated manually for unique monthly tuition + StudentMonthlyFee

import django.db.models.deletion
from decimal import Decimal
from django.db import migrations, models


def dedupe_fee_structures(apps, schema_editor):
    FeeStructure = apps.get_model("fees", "FeeStructure")
    Invoice = apps.get_model("fees", "Invoice")

    seen = {}
    for row in FeeStructure.objects.order_by("school_id", "class_level_id", "-id"):
        key = (row.school_id, row.class_level_id)
        if key not in seen:
            seen[key] = row.id
            continue
        keep_id = seen[key]
        Invoice.objects.filter(fee_structure_id=row.id).update(fee_structure_id=keep_id)
        row.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("academics", "0002_initial"),
        ("schools", "0001_initial"),
        ("students", "0001_initial"),
        ("fees", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(dedupe_fee_structures, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="feestructure",
            name="name",
            field=models.CharField(default="Monthly Tuition", max_length=100),
        ),
        migrations.AlterModelOptions(
            name="feestructure",
            options={"ordering": ["class_level__order", "class_level__name", "id"]},
        ),
        migrations.AddConstraint(
            model_name="feestructure",
            constraint=models.UniqueConstraint(
                fields=("school", "class_level"),
                name="fee_structure_unique_monthly_per_class",
            ),
        ),
        migrations.CreateModel(
            name="StudentMonthlyFee",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("base_amount", models.DecimalField(decimal_places=2, max_digits=10)),
                (
                    "discount_amount",
                    models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=10),
                ),
                ("notes", models.CharField(blank=True, max_length=255)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "fee_structure",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="student_monthly_fees",
                        to="fees.feestructure",
                    ),
                ),
                (
                    "school",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="student_monthly_fees",
                        to="schools.school",
                    ),
                ),
                (
                    "student",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="monthly_fee",
                        to="students.student",
                    ),
                ),
            ],
            options={
                "ordering": ["-updated_at", "-id"],
            },
        ),
    ]
