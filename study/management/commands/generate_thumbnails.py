from django.core.management.base import BaseCommand
from study.models import StudyResource
from study.constants import ResourceType

class Command(BaseCommand):
    help = 'Generate thumbnails for video resources without one'

    def handle(self, *args, **options):
        videos = StudyResource.objects.filter(
            resource_type=ResourceType.VIDEO,
            thumbnail__isnull=True
        )
        
        count = 0
        for video in videos:
            try:
                video.generate_thumbnail()
                video.save()
                count += 1
                self.stdout.write(f'Generated thumbnail for {video.title}')
            except Exception as e:
                self.stderr.write(f'Error for {video.title}: {str(e)}')
        
        self.stdout.write(self.style.SUCCESS(f'Generated {count} thumbnails'))