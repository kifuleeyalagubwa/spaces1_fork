# exams/apps.py
from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class ExamsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'exams'
    
    def ready(self):
        # Import signals and other initialization here
        # This runs AFTER Django is fully loaded
        try:
            from . import signals
            logger.info("Exams app signals loaded")
        except Exception as e:
            logger.error(f"Error loading exams signals: {str(e)}")