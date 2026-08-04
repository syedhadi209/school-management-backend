from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("schools", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="school",
            name="timezone",
            field=models.CharField(
                default="Asia/Karachi",
                help_text="IANA timezone used for timetable and attendance local-time resolution.",
                max_length=64,
            ),
        ),
    ]
