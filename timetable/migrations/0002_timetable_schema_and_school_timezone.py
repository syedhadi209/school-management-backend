import django.db.models.deletion
from django.db import migrations, models


def clear_timetable_entries(apps, schema_editor):
    TimetableEntry = apps.get_model("timetable", "TimetableEntry")
    TimetableEntry.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("academics", "0001_initial"),
        ("accounts", "0001_initial"),
        ("schools", "0002_school_timezone"),
        ("timetable", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(clear_timetable_entries, migrations.RunPython.noop),
        migrations.AlterUniqueTogether(
            name="timetableentry",
            unique_together=set(),
        ),
        migrations.RemoveField(
            model_name="timetableentry",
            name="period_label",
        ),
        migrations.AddField(
            model_name="timetableentry",
            name="end_time",
            field=models.TimeField(default="08:00:00"),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="timetableentry",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="timetableentry",
            name="label",
            field=models.CharField(blank=True, max_length=60),
        ),
        migrations.AddField(
            model_name="timetableentry",
            name="slot_type",
            field=models.CharField(
                choices=[("lecture", "Lecture"), ("break", "Break")],
                default="lecture",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="timetableentry",
            name="start_time",
            field=models.TimeField(default="07:00:00"),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="timetableentry",
            name="day_of_week",
            field=models.PositiveSmallIntegerField(
                choices=[
                    (0, "Monday"),
                    (1, "Tuesday"),
                    (2, "Wednesday"),
                    (3, "Thursday"),
                    (4, "Friday"),
                    (5, "Saturday"),
                    (6, "Sunday"),
                ]
            ),
        ),
        migrations.AlterField(
            model_name="timetableentry",
            name="subject",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="timetable_entries",
                to="academics.subject",
            ),
        ),
        migrations.AlterField(
            model_name="timetableentry",
            name="teacher",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="timetable_entries",
                to="accounts.teacherprofile",
            ),
        ),
        migrations.AddIndex(
            model_name="timetableentry",
            index=models.Index(
                fields=["school", "academic_year", "day_of_week", "start_time"],
                name="tt_school_year_day_start_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="timetableentry",
            index=models.Index(
                fields=["teacher", "day_of_week", "start_time"],
                name="tt_teacher_day_start_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="timetableentry",
            index=models.Index(
                fields=["section", "day_of_week", "start_time"],
                name="tt_section_day_start_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="timetableentry",
            constraint=models.CheckConstraint(
                condition=models.Q(("start_time__lt", models.F("end_time"))),
                name="tt_start_before_end",
            ),
        ),
    ]
