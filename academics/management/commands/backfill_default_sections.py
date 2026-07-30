from django.core.management.base import BaseCommand

from academics.models import ClassLevel
from academics.services import get_or_create_default_section


class Command(BaseCommand):
    help = "Ensure every class has at least one section so it appears in student pickers."

    def handle(self, *args, **options):
        created = 0
        for class_level in ClassLevel.objects.filter(sections__isnull=True).select_related("school"):
            section = get_or_create_default_section(class_level)
            created += 1
            self.stdout.write(
                f"{class_level.school.name} / {class_level.name}: created section {section.name}"
            )

        self.stdout.write(self.style.SUCCESS(f"Done. Sections created: {created}"))
