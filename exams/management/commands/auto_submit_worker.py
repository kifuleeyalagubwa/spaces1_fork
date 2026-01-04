import time
import logging
import traceback
import requests
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from django.conf import settings
from exams.services.redis_service import redis_service
from exams.models import ExamAttempt, Answer
from exams.constants import ATTEMPT_STATUS_AUTO_SUBMITTED

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Processes auto-submission of timed-out exam attempts'
    
    def _log_to_file(self, message):
        """Log messages to a dedicated file"""
        with open("auto_submit_worker.log", "a") as f:
            f.write(f"[{timezone.now()}] {message}\n")
    
    def handle(self, *args, **options):
        self._log_to_file("🚀 Starting enhanced auto-submit worker")
        logger.info("🚀 Starting enhanced auto-submit worker")
        logger.info("🔍 Press Ctrl+C to stop the worker")
        
        while True:
            try:
                due_attempt_ids = redis_service.get_due_auto_submits()
                
                if not due_attempt_ids:
                    time.sleep(5)
                    continue
                
                self._log_to_file(f"🔔 Found {len(due_attempt_ids)} due attempts")
                logger.info(f"🔔 Found {len(due_attempt_ids)} due attempts")
                
                for attempt_id in due_attempt_ids:
                    try:
                        self._log_to_file(f"Processing attempt {attempt_id}")
                        
                        with transaction.atomic():
                            attempt = ExamAttempt.objects.select_for_update().get(id=attempt_id)
                            
                            if attempt.status != 'IN_PROGRESS':
                                self._log_to_file(f"⚠️ Attempt already submitted (status: {attempt.status})")
                                redis_service.clear_auto_submit(attempt_id)
                                continue
                            
                            # Log time details
                            time_elapsed = timezone.now() - attempt.start_time
                            exam_duration = attempt.exam_set.duration_minutes * 60
                            
                            self._log_to_file(f"⏱️ Time elapsed: {time_elapsed.total_seconds():.1f}s")
                            self._log_to_file(f"⏱️ Exam duration: {exam_duration}s")
                            
                            # Submit via the same endpoint as manual submission
                            self._log_to_file("🚀 Submitting via endpoint...")
                            
                            # Create a POST request to the submit endpoint
                            session = requests.Session()
                            response = session.post(
                                f"http://{settings.ALLOWED_HOSTS[0]}:8000/exams/attempt/{attempt_id}/submit/",
                                data={'auto_submit': '1'},
                                headers={
                                    'X-Requested-With': 'XMLHttpRequest',
                                    'Referer': f'http://{settings.ALLOWED_HOSTS[0]}:8000/exams/attempt/{attempt_id}/'
                                }
                            )
                            
                            if response.status_code == 302:
                                self._log_to_file("✅ Submission successful!")
                                # Update attempt status in our record
                                attempt.refresh_from_db()
                                if attempt.status == ATTEMPT_STATUS_AUTO_SUBMITTED:
                                    self._log_to_file(f"🎉 Status updated to AUTO_SUBMITTED")
                                else:
                                    self._log_to_file(f"⚠️ Unexpected status after submit: {attempt.status}")
                            else:
                                self._log_to_file(f"❌ Submission failed: HTTP {response.status_code}")
                            
                            # Cleanup Redis
                            redis_service.clear_auto_submit(attempt_id)
                            redis_service.delete_attempt_state(attempt_id)
                    
                    except ExamAttempt.DoesNotExist:
                        self._log_to_file(f"❌ Attempt {attempt_id} does not exist")
                        redis_service.clear_auto_submit(attempt_id)
                    
                    except Exception as e:
                        self._log_to_file(f"🔥 ERROR: {str(e)}")
                        self._log_to_file(traceback.format_exc())
                        logger.error(f"Error processing attempt {attempt_id}: {str(e)}")
                        logger.error(traceback.format_exc())
                
                # Pause after processing batch
                time.sleep(1)
            
            except KeyboardInterrupt:
                self._log_to_file("🛑 Worker stopped by user")
                logger.info("🛑 Stopping auto-submit worker...")
                break
            
            except Exception as e:
                self._log_to_file(f"🔥🔥 CRITICAL ERROR: {str(e)}")
                self._log_to_file(traceback.format_exc())
                logger.critical(f"Critical error in worker: {str(e)}")
                logger.critical(traceback.format_exc())
                time.sleep(10)