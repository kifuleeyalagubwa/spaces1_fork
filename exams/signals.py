# exams/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import ExamSet, Question,ExamAttempt
from .constants import QUESTION_TYPE_TEXT  # Import the constant
from .services.redis_service import redis_service
from django.utils import timezone

@receiver(post_save, sender=ExamAttempt)
def schedule_auto_submit(sender, instance, created, **kwargs):
    if created and instance.status == 'IN_PROGRESS' and instance.is_first_attempt:
        # Schedule auto-submit in Redis
        redis_service.schedule_auto_submit(
            str(instance.id),
            instance.exam_set.duration_minutes
        )
        # Log scheduling
        with open("exam_monitor.log", "a") as f:
            f.write(f"[{timezone.now()}] SCHEDULED: Attempt {instance.id} for {instance.exam_set.title}\n")

@receiver(post_save, sender=Question)
def update_exam_set_reward_eligibility(sender, instance, **kwargs):
    exam_set = instance.exam_set
    # Use the constant value (which is 'TEXT')
    if exam_set and instance.question_type == QUESTION_TYPE_TEXT:
        if exam_set.reward_eligible:
            exam_set.reward_eligible = False
            exam_set.save(update_fields=['reward_eligible'])

@receiver(post_save, sender=ExamSet)
def initial_exam_set_check(sender, instance, created, **kwargs):
    if created:
        # Use the constant value here too
        if instance.questions.filter(question_type=QUESTION_TYPE_TEXT).exists():
            if instance.reward_eligible:
                instance.reward_eligible = False
                instance.save(update_fields=['reward_eligible'])

@receiver(post_save, sender=ExamSet)
def generate_exam_set_hash(sender, instance, created, **kwargs):
    if created and not instance.immutable_hash:
        instance.immutable_hash = instance.generate_hash()
        instance.save(update_fields=['immutable_hash'])
        
        

