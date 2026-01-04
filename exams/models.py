# exams/models.py
import uuid
import hashlib
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.conf import settings
from django.db.models import Q
from trends.models import *
from .constants import (
    QUESTION_TYPE_MCQ, QUESTION_TYPE_TEXT, QUESTION_TYPE_CHOICES,
    EXAM_SET_TYPE_FREE, EXAM_SET_TYPE_PREMIUM, EXAM_SET_TYPE_REWARD, EXAM_SET_TYPE_CHOICES,
    ATTEMPT_STATUS_IN_PROGRESS, ATTEMPT_STATUS_SUBMITTED, ATTEMPT_STATUS_AUTO_SUBMITTED,
    ATTEMPT_STATUS_GRADING_PENDING, ATTEMPT_STATUS_GRADED, ATTEMPT_STATUS_CHOICES,
    GRADING_CORRECT, GRADING_INCORRECT, GRADING_CHOICES
)
from .services.redis_service import redis_service
import time
from django.db import transaction  # Add this import at the top

class ExamSet(UUIDMixin):
    title = models.CharField(max_length=200)
    description = models.TextField()
    creator = models.ForeignKey(User, on_delete=models.CASCADE)
    set_type = models.CharField(max_length=10, choices=EXAM_SET_TYPE_CHOICES, default=EXAM_SET_TYPE_FREE)
    credits_required = models.PositiveIntegerField(default=0)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    topic = models.ForeignKey(Topic, on_delete=models.SET_NULL, null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(default=30)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    immutable_hash = models.CharField(max_length=64, blank=True)
    reward_eligible = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    @property
    def uid(self):
        return f"exm-{str(self.id)[:7]}"
    
    def save(self, *args, **kwargs):
        # First save to create primary key
        created = not self.pk
        super().save(*args, **kwargs)
        
        # Now we can safely check relationships
        if self.questions.filter(question_type=QUESTION_TYPE_TEXT).exists():
            # Only update if reward_eligible is currently True
            if self.reward_eligible:
                self.reward_eligible = False
                # Save only the reward_eligible field to avoid recursion
                super().save(update_fields=['reward_eligible'])
    
    def generate_hash(self):
        """Generate hash for blockchain immutability"""
        if not self.id or not self.created_at:
            return ""
        content = f"{self.id}{self.title}{self.description}{self.created_at.timestamp()}"
        return hashlib.sha256(content.encode()).hexdigest()

class Question(UUIDMixin):
    exam_set = models.ForeignKey(ExamSet, on_delete=models.CASCADE, related_name='questions')
    question_type = models.CharField(max_length=10, choices=QUESTION_TYPE_CHOICES)
    text = models.TextField()
    order = models.PositiveIntegerField(default=0)
    points = models.PositiveIntegerField(default=1)
    
    # Fields specific to MCQ questions
    choices = models.JSONField(default=list, blank=True, null=True)
    correct_choice = models.CharField(max_length=1, blank=True, null=True)
    
    # Fields specific to Text questions
    reference_answer = models.TextField(blank=True, null=True)
    max_length = models.PositiveIntegerField(default=500, blank=True, null=True)
    
    class Meta:
        ordering = ['order']
    
    def __str__(self):
        return f"{self.text[:50]}..."
    
    @property
    def uid(self):
        return f"que-{str(self.id)[:7]}"
    
    def clean(self):
        if self.question_type == QUESTION_TYPE_MCQ:
            # Validate choices for MCQ
            if not isinstance(self.choices, list):
                raise ValidationError("Choices must be a list")
            
            if len(self.choices) < 2:
                raise ValidationError("At least two choices are required")
            
            for choice in self.choices:
                if 'letter' not in choice or 'text' not in choice:
                    raise ValidationError("Each choice must have 'letter' and 'text' properties")
            
            # Validate correct choice
            choice_letters = [c['letter'] for c in self.choices]
            if self.correct_choice and self.correct_choice not in choice_letters:
                raise ValidationError("Correct choice must be one of the provided options")
        
        elif self.question_type == QUESTION_TYPE_TEXT:
            # Validate reference answer for text questions
            if not self.reference_answer:
                raise ValidationError("Reference answer is required for text questions")

class ExamAttempt(UUIDMixin):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='exam_attempts')
    exam_set = models.ForeignKey(ExamSet, on_delete=models.CASCADE, related_name='attempts')
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=ATTEMPT_STATUS_CHOICES, default=ATTEMPT_STATUS_IN_PROGRESS)
    browser_leaves = models.PositiveIntegerField(default=0)
    final_score = models.FloatField(null=True, blank=True)
    graded_at = models.DateTimeField(null=True, blank=True)
    is_first_attempt = models.BooleanField(default=False)
    submission_hash = models.CharField(max_length=64, blank=True)
    assessment_hash = models.CharField(max_length=64, blank=True)
    
    class Meta:
        ordering = ['-start_time']
    
    @property
    def time_remaining(self):
        if self.end_time:
            return 0
        elapsed = timezone.now() - self.start_time
        remaining_seconds = self.exam_set.duration_minutes * 60 - elapsed.total_seconds()
        return max(0, remaining_seconds)
    
    def generate_submission_hash(self):
        """Generate hash of all answers for immutability"""
        answers = self.answers.select_related('question').order_by('question__order')
        data = f"{self.id}{self.start_time.timestamp()}"
        
        for answer in answers:
            if answer.question.question_type == QUESTION_TYPE_MCQ:
                data += f"{answer.question.id}{answer.mcq_answer}"
            else:
                data += f"{answer.question.id}{answer.text_answer}"
                
        return hashlib.sha256(data.encode()).hexdigest()
    
    def generate_assessment_hash(self):
        """Generate hash after grading for blockchain"""
        data = self.submission_hash
        
        # Include grading decisions for text questions
        gradings = self.gradings.select_related('question').order_by('question__order')
        for grading in gradings:
            data += f"{grading.question.id}{grading.is_correct}"
            
        return hashlib.sha256(data.encode()).hexdigest()
    
    
    def save(self, *args, **kwargs):
        # First save to create primary key and set start_time
        created = not self.pk
        super().save(*args, **kwargs)
        
        # Only apply Redis to first attempts after save
        if created and self.is_first_attempt and self.status == ATTEMPT_STATUS_IN_PROGRESS:
            # Now start_time is set
            redis_data = {
                'user_id': str(self.user.id),
                'exam_set_id': str(self.exam_set.id),
                'start_time': str(self.start_time.timestamp()),
                'browser_leaves': str(self.browser_leaves),
                'is_first_attempt': str(self.is_first_attempt)
            }
            ttl = self.exam_set.duration_minutes * 60 + 300
            redis_service.cache_attempt_state(str(self.id), redis_data, ttl)
            
            # Schedule auto-submit
            redis_service.schedule_auto_submit(
                str(self.id),
                self.exam_set.duration_minutes
            )
    
    

    def auto_grade_mcqs(self):
        """Grade only MCQ questions and return earned_points, total_points"""
        mcq_answers = self.answers.filter(question__question_type=QUESTION_TYPE_MCQ)
        total_points = 0
        earned_points = 0
        
        for answer in mcq_answers:
            question = answer.question
            user_choice = (answer.mcq_answer or '').strip().upper()
            correct_choice = (question.correct_choice or '').strip().upper()
            
            answer.is_correct = (user_choice == correct_choice)
            answer.save()
            
            total_points += question.points
            if answer.is_correct:
                earned_points += question.points
        
        return earned_points, total_points

    def calculate_final_score(self):
        """Calculate final score including both MCQs and text questions"""
        total_points = 0
        earned_points = 0
        
        # Grade MCQs
        mcq_earned, mcq_total = self.auto_grade_mcqs()
        earned_points += mcq_earned
        total_points += mcq_total
        
        # Include text questions if graded
        text_answers = self.answers.filter(question__question_type=QUESTION_TYPE_TEXT)
        for answer in text_answers:
            question = answer.question
            grading = Grading.objects.filter(attempt=self, question=question).first()
            
            total_points += question.points
            if grading and grading.is_correct:
                earned_points += question.points
        
        return (earned_points / total_points * 100) if total_points > 0 else 0

    

    def mark_as_submitted(self, auto_submitted=False):
        with transaction.atomic():
            # Ensure answers are saved first
            answers = list(self.answers.all())
            for answer in answers:
                answer.save()
            
            self.end_time = timezone.now()
            self.status = ATTEMPT_STATUS_AUTO_SUBMITTED if auto_submitted else ATTEMPT_STATUS_SUBMITTED
            
            # Grade MCQs immediately
            mcq_earned, mcq_total = self.auto_grade_mcqs()
            
            # Calculate final score
            total_points = mcq_total
            earned_points = mcq_earned
            
            # Include text questions if graded
            text_answers = self.answers.filter(question__question_type=QUESTION_TYPE_TEXT)
            for answer in text_answers:
                total_points += answer.question.points
                if answer.gradings.exists() and answer.gradings.first().is_correct:
                    earned_points += answer.question.points
            
            self.final_score = (earned_points / total_points * 100) if total_points > 0 else 0
            
            # Status handling
            if self.is_first_attempt:
                self.submission_hash = self.generate_submission_hash()
                if text_answers.exists():
                    self.status = ATTEMPT_STATUS_GRADING_PENDING
                else:
                    self.status = ATTEMPT_STATUS_GRADED
                    self.graded_at = timezone.now()
                    self.assessment_hash = self.generate_assessment_hash()
            else:
                self.status = ATTEMPT_STATUS_GRADED
                self.graded_at = timezone.now()
            
            self.save()           
                
        
        def auto_grade(self):
            total_points = 0
            earned_points = 0
            
            for answer in self.answers.all():
                question = answer.question
                
                if question.question_type == QUESTION_TYPE_MCQ:
                    # Normalize choices for comparison
                    user_choice = (answer.mcq_answer or '').strip().upper()
                    correct_choice = (question.correct_choice or '').strip().upper()
                    
                    answer.is_correct = (user_choice == correct_choice)
                    answer.save()
                    
                    total_points += question.points
                    if answer.is_correct:
                        earned_points += question.points
            
            self.final_score = (earned_points / total_points * 100) if total_points > 0 else 0
            self.status = ATTEMPT_STATUS_GRADED
            self.graded_at = timezone.now()
            
            # Generate final assessment hash ONLY for first attempts
            if self.is_first_attempt:
                self.assessment_hash = self.generate_assessment_hash()
            
            self.save()
        
        def delete(self, *args, **kwargs):
            redis_service.delete_attempt_state(str(self.id))
            redis_service.clear_auto_submit(str(self.id))
            super().delete(*args, **kwargs)
        
        
        
        @property
        def uid(self):
            return f"att-{str(self.id)[:7]}"     

class Answer(UUIDMixin):
    attempt = models.ForeignKey(ExamAttempt, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    mcq_answer = models.CharField(max_length=1, blank=True, null=True)
    text_answer = models.TextField(blank=True, null=True)
    is_correct = models.BooleanField(null=True)  # For MCQs
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    
    class Meta:
        unique_together = [('attempt', 'question')]
    
    def clean(self):
        # Only validate if question is set
        if hasattr(self, 'question') and self.question:
            if self.question.question_type == QUESTION_TYPE_MCQ and not self.mcq_answer:
                raise ValidationError("MCQ question requires an answer choice")
            if self.question.question_type == QUESTION_TYPE_TEXT and not self.text_answer:
                raise ValidationError("Text question requires an answer")

class Grading(UUIDMixin):
    attempt = models.ForeignKey(ExamAttempt, on_delete=models.CASCADE, related_name='gradings')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)  # Changed from TextQuestion
    is_correct = models.BooleanField()
    graded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='graded_questions')
    graded_at = models.DateTimeField(auto_now_add=True)
    feedback = models.TextField(blank=True, null=True)
    
    class Meta:
        unique_together = [('attempt', 'question')]

class Correction(UUIDMixin):
    exam_set = models.ForeignKey(ExamSet, on_delete=models.CASCADE, related_name='corrections')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)  # Changed to unified Question
    explanation = models.TextField()
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = [('exam_set', 'question')]
    
    @property
    def uid(self):
        return f"cor-{str(self.id)[:7]}"

class TextAssessmentSession(UUIDMixin):
    setter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assessment_sessions')
    attempt = models.ForeignKey(ExamAttempt, on_delete=models.CASCADE, related_name='assessment_sessions')
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)
    immutable_hash = models.CharField(max_length=64, blank=True)

    def generate_hash(self):
        content = f"{self.id}{self.setter.id}{self.attempt.id}{self.created_at.timestamp()}"
        return hashlib.sha256(content.encode()).hexdigest()
    
    def mark_as_completed(self):
        self.completed_at = timezone.now()
        self.is_completed = True
        self.immutable_hash = self.generate_hash()
        self.save()

class TextQuestionAssessment(UUIDMixin):
    session = models.ForeignKey(TextAssessmentSession, on_delete=models.CASCADE, related_name='assessments')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)  # Changed to unified Question
    score = models.PositiveIntegerField()
    feedback = models.TextField(blank=True, null=True)
    assessed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = [('session', 'question')]