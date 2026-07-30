from django.core.management.base import BaseCommand

from schools.models import School
from schools.services import get_or_create_default_academic_year


class Command(BaseCommand):
    help = "Ensure every school has at least one academic year."

    def handle(self, *args, **options):
        created = 0
        for school in School.objects.all():
            had_year = school.academic_years.exists()
            academic_year = get_or_create_default_academic_year(school)
            if not had_year:
                created += 1
                self.stdout.write(f"{school.name}: created academic year {academic_year.name}")

        self.stdout.write(self.style.SUCCESS(f"Done. Academic years created: {created}"))
