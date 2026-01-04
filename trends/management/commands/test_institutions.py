# trends/management/commands/test_institutions.py
from django.core.management.base import BaseCommand
from trends.models import Institution, User, Profile

class Command(BaseCommand):
    help = 'Test institution setup and subdomains'

    def handle(self, *args, **options):
        # List all institutions
        institutions = Institution.objects.all()
        
        self.stdout.write(
            self.style.SUCCESS(f"Found {institutions.count()} institutions:")
        )
        
        for institution in institutions:
            self.stdout.write(f"""
            Institution: {institution.name}
            Subdomain: {institution.subdomain}
            Type: {institution.get_institution_type_display()}
            Admin: {institution.admin.username}
            Approved: {institution.is_approved}
            Active: {institution.is_active}
            
            Access URLs:
            - Main site: http://127.0.0.1:8000/
            - Subdomain: http://{institution.subdomain}.127.0.0.1:8000/
            - Localhost: http://{institution.subdomain}.localhost:8000/
            - Switch: http://127.0.0.1:8000/institution/switch/
            """)