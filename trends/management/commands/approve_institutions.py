# trends/management/commands/approve_institutions.py
from django.core.management.base import BaseCommand
from trends.models import Institution

class Command(BaseCommand):
    help = 'Approve all institutions for testing'

    def handle(self, *args, **options):
        updated = Institution.objects.update(is_approved=True)
        self.stdout.write(
            self.style.SUCCESS(f"Approved {updated} institutions")
        )