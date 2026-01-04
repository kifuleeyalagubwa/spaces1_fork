import json
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DetailView
from django.urls import reverse
from django.utils import timezone
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from .models import *
from .forms import (
    ExamSetForm, MCQQuestionForm, TextQuestionForm, 
    AnswerForm, GradingForm, CorrectionForm
)
from .services.redis_service import redis_service
from trends.models import User
from django.utils import timezone
from django.db.models import Count, Q
from .constants import QUESTION_TYPE_MCQ, QUESTION_TYPE_TEXT



class ExamSetListView(LoginRequiredMixin, ListView):
    model = ExamSet
    template_name = 'exams/exam_set_list.html'
    context_object_name = 'exam_sets'
    
    def get_queryset(self):
        if self.request.user.profile.role == 'setter':
            return ExamSet.objects.filter(creator=self.request.user)
        return ExamSet.objects.filter(is_active=True)

# exams/views.py
def exam_set_create(request):
    if request.method == 'POST':
        form = ExamSetForm(request.POST)
        if form.is_valid():
            # Create but don't save yet
            instance = form.save(commit=False)
            # Set the creator to current user
            instance.creator = request.user
            # Now save to create primary key
            instance.save()
            # Save many-to-many relationships if any
            form.save_m2m()
            return redirect('exams:exam_set_detail', pk=instance.pk)
        else:
            # Print form errors to console for debugging
            print("Form errors:", form.errors)
    else:
        form = ExamSetForm()
    
    return render(request, 'exams/exam_set_form.html', {'form': form})
    
class ExamSetUpdateView(LoginRequiredMixin, UpdateView):
    model = ExamSet
    form_class = ExamSetForm
    template_name = 'exams/exam_set_form.html'
    
    def get_success_url(self):
        return reverse('exams:exam_set_detail', kwargs={'pk': self.object.pk})


class ExamSetDetailView(LoginRequiredMixin, DetailView):
    model = ExamSet
    template_name = 'exams/exam_set_detail.html'
    context_object_name = 'exam_set'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        exam_set = self.object
        
        # Count question types
        context['mcq_count'] = exam_set.questions.filter(question_type=QUESTION_TYPE_MCQ).count()
        context['text_count'] = exam_set.questions.filter(question_type=QUESTION_TYPE_TEXT).count()
        
        # Check if user has already taken this exam
        if self.request.user.is_authenticated:
            first_attempt = ExamAttempt.objects.filter(
                user=self.request.user,
                exam_set=exam_set,
                is_first_attempt=True
            ).first()
            context['has_first_attempt'] = bool(first_attempt)
        
        return context        
        
class QuestionCreateView(LoginRequiredMixin, CreateView):
    template_name = 'exams/question_form.html'
    
    def get_form_class(self):
        question_type = self.request.GET.get('type')
        if question_type == QUESTION_TYPE_MCQ:
            return MCQQuestionForm
        return TextQuestionForm
    
    def get_template_names(self):
        question_type = self.request.GET.get('type')
        if question_type == QUESTION_TYPE_MCQ:
            return ['exams/mcq_question_form.html']
        return ['exams/text_question_form.html']
    
    def form_valid(self, form):
        form.instance.exam_set = get_object_or_404(ExamSet, pk=self.kwargs['exam_set_id'])
        form.instance.created_by = self.request.user
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('exams:exam_set_detail', kwargs={'pk': self.kwargs['exam_set_id']})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['exam_set'] = get_object_or_404(ExamSet, pk=self.kwargs['exam_set_id'])
        return context

class QuestionUpdateView(LoginRequiredMixin, UpdateView):
    model = Question
    template_name = 'exams/question_form.html'
    
    def get_form_class(self):
        if self.object.question_type == QUESTION_TYPE_MCQ:
            return MCQQuestionForm
        return TextQuestionForm
    
    def get_template_names(self):
        if self.object.question_type == QUESTION_TYPE_MCQ:
            return ['exams/mcq_question_form.html']
        return ['exams/text_question_form.html']
    
    def get_success_url(self):
        return reverse('exams:exam_set_detail', kwargs={'pk': self.object.exam_set.id})

class ExamAttemptStartView(LoginRequiredMixin, View):
    def get(self, request, pk):
        exam_set = get_object_or_404(ExamSet, pk=pk)
        
        # Check credits for premium exams
        if exam_set.set_type == 'PREMIUM' and request.user.credits < exam_set.credits_required:
            messages.warning(request, "You don't have enough credits to take this exam")
            return redirect('exams:exam_set_detail', pk=pk)
        
        # Check if ANY attempt exists (not just first)
        any_attempt_exists = ExamAttempt.objects.filter(
            user=request.user,
            exam_set=exam_set
        ).exists()
        
        # This is a REAL first attempt only if NO previous attempts exist
        is_real_first_attempt = not any_attempt_exists
        
        # Create exam attempt
        start_time = timezone.now()
        attempt = ExamAttempt.objects.create(
            user=request.user,
            exam_set=exam_set,
            is_first_attempt=is_real_first_attempt,  # True ONLY if truly first attempt
            start_time=start_time
        )
        
        # Initialize Redis state for ALL attempts (for timer/browser tracking)
        redis_data = {
            'user_id': str(request.user.id),
            'exam_set_id': str(exam_set.id),
            'start_time': str(start_time.timestamp()),
            'browser_leaves': '0',
            'is_first_attempt': str(is_real_first_attempt),
            'current_question': '0'
        }
        redis_service.cache_attempt_state(
            str(attempt.id),
            redis_data,
            exam_set.duration_minutes * 60 + 300
        )
        
        # Schedule auto-submit ONLY for REAL first attempts
        if is_real_first_attempt:
            redis_service.schedule_auto_submit(
                str(attempt.id),
                exam_set.duration_minutes
            )
        
        return redirect('exams:exam_interface', pk=attempt.id)



class ExamInterfaceView(LoginRequiredMixin, View):
    def get(self, request, pk):
        attempt = get_object_or_404(ExamAttempt, pk=pk, user=request.user)
        
        # Redirect if already submitted
        if attempt.status != 'IN_PROGRESS':
            return redirect('exams:exam_result', pk=attempt.id)
        
        # Get all questions
        questions = list(attempt.exam_set.questions.order_by('order'))
        total_questions = len(questions)
        
        # Get current question index from Redis
        redis_data = redis_service.get_attempt_state(str(attempt.id)) or {}
        current_index = int(redis_data.get('current_question', 0))
        
        # Handle navigation from question buttons
        if 'go_to' in request.GET:
            go_to = int(request.GET.get('go_to'))
            if 0 <= go_to < total_questions:
                current_index = go_to
                # Update Redis state
                redis_data['current_question'] = str(current_index)
                redis_service.cache_attempt_state(str(attempt.id), redis_data)
        
        # Prepare form for current question
        question = questions[current_index]
        try:
            existing_answer = Answer.objects.get(attempt=attempt, question=question)
            form = AnswerForm(question=question, instance=existing_answer)
        except Answer.DoesNotExist:
            form = AnswerForm(question=question)
        
        # Calculate time remaining
        time_remaining_seconds = int(attempt.time_remaining)
        minutes = time_remaining_seconds // 60
        seconds = time_remaining_seconds % 60
        time_remaining_display = f"{minutes}:{seconds:02d}"
        
        # Calculate progress
        progress_percent = int((current_index / total_questions) * 100)
        
        # Count answered questions
        answered_count = attempt.answers.values('question').distinct().count()
        unanswered_count = total_questions - answered_count
        
        context = {
            'attempt': attempt,
            'question': question,
            'questions': questions,
            'current_index': current_index,
            'total_questions': total_questions,
            'form': form,
            'is_first_attempt': attempt.is_first_attempt,
            'progress_percent': progress_percent,
            'time_remaining_display': time_remaining_display,
            'time_remaining_seconds': time_remaining_seconds,
            'question_range': range(total_questions),
            'unanswered_count': unanswered_count,
        }
        return render(request, 'exams/exam_interface.html', context)
    
    def post(self, request, pk):
        attempt = get_object_or_404(ExamAttempt, pk=pk, user=request.user)
        
        # Handle browser leave event
        if request.POST.get('type') == 'browser_leave':
            redis_data = redis_service.get_attempt_state(str(attempt.id)) or {}
            leaves = int(redis_data.get('browser_leaves', 0)) + 1
            redis_service.cache_attempt_state(
                str(attempt.id),
                {**redis_data, 'browser_leaves': str(leaves)}
            )
            return JsonResponse({'status': 'leave recorded', 'count': leaves})
        
        # Save answer
        question = get_object_or_404(Question, pk=request.POST.get('question_id'))
        form = AnswerForm(request.POST, question=question)
        
        if form.is_valid():
            Answer.objects.update_or_create(
                attempt=attempt,
                question=question,
                defaults={
                    'mcq_answer': form.cleaned_data.get('mcq_answer'),
                    'text_answer': form.cleaned_data.get('text_answer')
                }
            )
        
        redis_data = redis_service.get_attempt_state(str(attempt.id)) or {}
        current_index = int(redis_data.get('current_question', 0))
        total_questions = attempt.exam_set.questions.count()
        
        # Handle navigation
        if 'go_to' in request.POST:
            new_index = int(request.POST.get('go_to'))
            if 0 <= new_index < total_questions:
                redis_data['current_question'] = str(new_index)
                redis_service.cache_attempt_state(str(attempt.id), redis_data)
                return redirect('exams:exam_interface', pk=attempt.id)
        
        # Determine next action
        if 'next' in request.POST and current_index < total_questions - 1:
            redis_data['current_question'] = str(current_index + 1)
            redis_service.cache_attempt_state(str(attempt.id), redis_data)
            return redirect('exams:exam_interface', pk=attempt.id)
        elif 'prev' in request.POST and current_index > 0:
            redis_data['current_question'] = str(current_index - 1)
            redis_service.cache_attempt_state(str(attempt.id), redis_data)
            return redirect('exams:exam_interface', pk=attempt.id)
        elif 'submit' in request.POST:
            return redirect('exams:exam_submit', pk=attempt.id)
        
        return redirect('exams:exam_interface', pk=attempt.id)

class ExamSubmitView(LoginRequiredMixin, View):
    def get(self, request, pk):
        attempt = get_object_or_404(ExamAttempt, pk=pk, user=request.user)
        
        # Calculate stats
        total_questions = attempt.exam_set.questions.count()
        answered_questions = attempt.answers.values('question').distinct().count()
        unanswered_count = total_questions - answered_questions
        
        # Calculate time spent
        time_spent = (timezone.now() - attempt.start_time).seconds // 60
        
        context = {
            'attempt': attempt,
            'is_first_attempt': attempt.is_first_attempt,
            'answered_count': answered_questions,
            'unanswered_count': unanswered_count,
            'total_questions': total_questions,
            'time_spent': time_spent,
        }
        return render(request, 'exams/exam_submit.html', context)
    
    def post(self, request, pk):
        attempt = get_object_or_404(ExamAttempt, pk=pk, user=request.user)
        
        # Handle both auto and manual submission
        is_auto_submit = 'auto_submit' in request.POST
        
        # Ensure answers are saved
        answers = attempt.answers.all()
        for answer in answers:
            answer.save()
        
        # Mark as submitted
        attempt.mark_as_submitted(auto_submitted=is_auto_submit)
        
        # Clear Redis state if first attempt
        if attempt.is_first_attempt:
            redis_service.delete_attempt_state(str(attempt.id))
            redis_service.clear_auto_submit(str(attempt.id))
        
        return redirect('exams:exam_result', pk=attempt.id)

        
class GradingDashboardView(LoginRequiredMixin, ListView):
    model = ExamAttempt
    template_name = 'exams/grading_dashboard.html'
    context_object_name = 'pending_attempts'
    
    def get_queryset(self):
        return ExamAttempt.objects.filter(
            status='GRADING_PENDING',
            exam_set__creator=self.request.user
        ).order_by('-end_time')

class GradingInterfaceView(LoginRequiredMixin, View):
    template_name = 'exams/grading_interface.html'
    
    def get(self, request, pk):
        attempt = get_object_or_404(ExamAttempt, pk=pk)
        # Get text questions directly from attempt's exam_set
        text_questions = attempt.exam_set.questions.filter(question_type=QUESTION_TYPE_TEXT)
        text_answers = Answer.objects.filter(
            attempt=attempt,
            question__in=text_questions
        ).select_related('question')
        
        redis_data = redis_service.get_attempt_state(str(attempt.id)) or {}
        current_index = int(redis_data.get('grading_index', 0))
        
        if text_answers:
            current_answer = text_answers[current_index]
            form = GradingForm(initial={
                'is_correct': True,
                'feedback': ''
            })
        else:
            current_answer = None
            form = None
        
        context = {
            'attempt': attempt,
            'answers': text_answers,
            'current_answer': current_answer,
            'current_index': current_index,
            'form': form,
            'total_questions': len(text_answers)
        }
        return render(request, self.template_name, context)
    
    def post(self, request, pk):
        attempt = get_object_or_404(ExamAttempt, pk=pk)
        answer = get_object_or_404(Answer, pk=request.POST.get('answer_id'))
        
        form = GradingForm(request.POST)
        if form.is_valid():
            Grading.objects.update_or_create(
                attempt=attempt,
                question=answer.question,
                defaults={
                    'is_correct': form.cleaned_data['is_correct'],
                    'feedback': form.cleaned_data['feedback'],
                    'graded_by': request.user
                }
            )
        
        text_answers = Answer.objects.filter(
            attempt=attempt,
            question__question_type=QUESTION_TYPE_TEXT
        ).order_by('question__order')
        total_questions = text_answers.count()
        
        redis_data = redis_service.get_attempt_state(str(attempt.id)) or {}
        current_index = int(redis_data.get('grading_index', 0))
        
        if 'next' in request.POST and current_index < total_questions - 1:
            redis_data['grading_index'] = str(current_index + 1)
            redis_service.cache_attempt_state(str(attempt.id), redis_data)
            return redirect('exams:grading_interface', pk=attempt.id)
        elif 'prev' in request.POST and current_index > 0:
            redis_data['grading_index'] = str(current_index - 1)
            redis_service.cache_attempt_state(str(attempt.id), redis_data)
            return redirect('exams:grading_interface', pk=attempt.id)
        
        return redirect('exams:grading_submit', pk=attempt.id)

class GradingSubmitView(LoginRequiredMixin, View):
    def post(self, request, pk):
        attempt = get_object_or_404(ExamAttempt, pk=pk)
        
        total_points = 0
        earned_points = 0
        
        # Process all answers (both MCQ and text)
        for answer in attempt.answers.all():
            question = answer.question
            total_points += question.points
            
            if question.question_type == QUESTION_TYPE_MCQ:
                # Already graded during submission
                if answer.is_correct:
                    earned_points += question.points
            elif question.question_type == QUESTION_TYPE_TEXT:
                # Get manual grading
                grading = Grading.objects.filter(
                    attempt=attempt, 
                    question=question
                ).first()
                
                if grading and grading.is_correct:
                    earned_points += question.points
        
        # Update attempt
        attempt.final_score = (earned_points / total_points * 100) if total_points > 0 else 0
        attempt.status = 'GRADED'
        attempt.graded_at = timezone.now()
        
        # Generate assessment hash ONLY for first attempts
        if attempt.is_first_attempt:
            attempt.assessment_hash = attempt.generate_assessment_hash()
        
        attempt.save()
        
        redis_service.delete_attempt_state(str(attempt.id))
        
        messages.success(request, "Grading completed successfully!")
        return redirect('exams:exam_result', pk=attempt.id)

class ExamResultView(LoginRequiredMixin, DetailView):
    model = ExamAttempt
    template_name = 'exams/exam_result.html'
    context_object_name = 'attempt'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        attempt = self.object
        
        # Log result view access
        with open("exam_monitor.log", "a") as f:
            f.write(f"[{timezone.now()}] RESULT_VIEW: Attempt {attempt.id} by {self.request.user.username}\n")
            f.write(f"   - Score: {attempt.final_score}%\n")
            f.write(f"   - Status: {attempt.status}\n")
            f.write(f"   - Auto-submitted: {attempt.status == 'AUTO_SUBMITTED'}\n")
        
        answers = attempt.answers.select_related('question').order_by('question__order')
        context['answers'] = answers
        
        # Log answer details
        with open("exam_monitor.log", "a") as f:
            f.write(f"   - Answer count: {answers.count()}\n")
            for answer in answers:
                f.write(f"      Q{answer.question.order}: ")
                if answer.question.question_type == 'MCQ':
                    f.write(f"MCQ: {answer.mcq_answer} (Correct: {answer.question.correct_choice})")
                else:
                    f.write(f"TEXT: {answer.text_answer[:50]}...")
                f.write(f" - Graded: {answer.is_correct}\n")
        
        correct_answers = 0
        incorrect_answers = 0
        
        for answer in answers:
            if answer.is_correct:
                correct_answers += 1
            else:
                incorrect_answers += 1
                
        context['correct_answers'] = correct_answers
        context['incorrect_answers'] = incorrect_answers
        
        # Add additional debugging info
        context['debug_info'] = {
            'submission_time': attempt.end_time,
            'grading_time': attempt.graded_at,
            'is_auto_submitted': attempt.status == 'AUTO_SUBMITTED',
            'answer_count': answers.count(),
            'first_attempt': attempt.is_first_attempt,
        }
        
        return context


class ExamResultListView(LoginRequiredMixin, ListView):
    model = ExamAttempt
    template_name = 'exams/exam_result_list.html'
    context_object_name = 'attempts'
    
    def get_queryset(self):
        return ExamAttempt.objects.filter(user=self.request.user).order_by('-start_time')

class CorrectionCreateView(LoginRequiredMixin, CreateView):
    model = Correction
    form_class = CorrectionForm
    template_name = 'exams/correction_form.html'
    
    def form_valid(self, form):
        exam_set = get_object_or_404(ExamSet, pk=self.kwargs['exam_set_id'])
        form.instance.exam_set = exam_set
        form.instance.created_by = self.request.user
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('exams:exam_set_detail', kwargs={'pk': self.kwargs['exam_set_id']})
        
class AssessmentDashboardView(LoginRequiredMixin, ListView):
    model = ExamAttempt
    template_name = 'exams/assessment_dashboard.html'
    context_object_name = 'pending_attempts'
    
    def get_queryset(self):
        return ExamAttempt.objects.filter(
            status='GRADING_PENDING',
            exam_set__creator=self.request.user
        ).order_by('-end_time')

class StartAssessmentView(LoginRequiredMixin, View):
    def get(self, request, pk):
        attempt = get_object_or_404(ExamAttempt, pk=pk)
        
        session = TextAssessmentSession.objects.create(
            setter=request.user,
            attempt=attempt
        )
        
        return redirect('exams:assessment_interface', session_id=session.id)

class AssessmentInterfaceView(LoginRequiredMixin, View):
    template_name = 'exams/assessment_interface.html'
    
    def get(self, request, session_id):
        session = get_object_or_404(TextAssessmentSession, pk=session_id, setter=request.user)
        attempt = session.attempt
        
        # Get unassessed text questions
        text_questions = attempt.exam_set.questions.filter(
            question_type=QUESTION_TYPE_TEXT
        ).exclude(
            id__in=session.assessments.values_list('question_id', flat=True)
        ).order_by('order')
        
        current_question = text_questions.first() if text_questions.exists() else None
        answer = None
        if current_question:
            answer = Answer.objects.filter(
                attempt=attempt,
                question=current_question
            ).first()
        
        context = {
            'session': session,
            'attempt': attempt,
            'question': current_question,
            'answer': answer,
            'remaining': text_questions.count(),
            'total_text_questions': attempt.exam_set.questions.filter(
                question_type=QUESTION_TYPE_TEXT).count(),
            'completed': session.assessments.count()
        }
        return render(request, self.template_name, context)
    
    def post(self, request, session_id):
        session = get_object_or_404(TextAssessmentSession, pk=session_id, setter=request.user)
        question_id = request.POST.get('question_id')
        question = get_object_or_404(Question, pk=question_id)
        
        TextQuestionAssessment.objects.create(
            session=session,
            question=question,
            score=int(request.POST.get('score', 0)),
            feedback=request.POST.get('feedback', '')
        )
        
        total_text_questions = session.attempt.exam_set.questions.filter(
            question_type=QUESTION_TYPE_TEXT).count()
        if session.assessments.count() >= total_text_questions:
            return redirect('exams:assessment_submit', session_id=session.id)
        
        return redirect('exams:assessment_interface', session_id=session.id)

class AssessmentSubmitView(LoginRequiredMixin, View):
    template_name = 'exams/assessment_submit.html'
    
    def get(self, request, session_id):
        session = get_object_or_404(TextAssessmentSession, pk=session_id, setter=request.user)
        return render(request, self.template_name, {'session': session})
    
    def post(self, request, session_id):
        session = get_object_or_404(TextAssessmentSession, pk=session_id, setter=request.user)
        session.mark_as_completed()
        
        total_points = 0
        earned_points = 0
        attempt = session.attempt
        
        # Process MCQ answers
        mcq_answers = attempt.answers.filter(question__question_type=QUESTION_TYPE_MCQ)
        for answer in mcq_answers:
            total_points += answer.question.points
            if answer.is_correct:
                earned_points += answer.question.points
        
        # Process text assessments
        for assessment in session.assessments.all():
            total_points += assessment.question.points
            earned_points += assessment.score
        
        # Update attempt
        attempt.final_score = (earned_points / total_points * 100) if total_points > 0 else 0
        attempt.status = 'GRADED'
        attempt.graded_at = timezone.now()
        
        if attempt.is_first_attempt:
            attempt.assessment_hash = attempt.generate_assessment_hash()
        
        attempt.save()
        
        messages.success(request, "Assessment completed successfully!")
        return redirect('exams:exam_result', pk=attempt.id)
        



def add_mcq_question(request, set_id):
    exam_set = get_object_or_404(ExamSet, id=set_id)
    
    if request.method == 'POST':
        form = MCQQuestionForm(request.POST)
        if form.is_valid():
            question = form.save(commit=False)
            question.exam_set = exam_set
            question.save()
            return redirect('exams:exam_set_detail', pk=exam_set.id)
    else:
        form = MCQQuestionForm()
    
    return render(request, 'exams/mcq_question_form.html', {
        'form': form,
        'exam_set': exam_set,
        'debug_data': request.POST if request.method == 'POST' else None
    })

def edit_mcq_question(request, set_id, question_id):
    exam_set = get_object_or_404(ExamSet, id=set_id)
    question = get_object_or_404(Question, id=question_id, exam_set=exam_set, question_type='MCQ')
    
    if request.method == 'POST':
        form = MCQQuestionForm(request.POST, instance=question)
        if form.is_valid():
            form.save()
            return redirect('exams:exam_set_detail', pk=exam_set.id)
    else:
        form = MCQQuestionForm(instance=question)
    
    return render(request, 'exams/mcq_question_form.html', {
        'form': form,
        'exam_set': exam_set,
        'question': question
    })

def add_text_question(request, set_id):
    exam_set = get_object_or_404(ExamSet, id=set_id)
    if request.method == 'POST':
        form = TextQuestionForm(request.POST)
        if form.is_valid():
            question = form.save(commit=False)
            question.exam_set = exam_set
            question.question_type = 'TEXT'  # Set the question type
            question.save()
            return redirect('exam_set_detail', pk=exam_set.id)
    else:
        form = TextQuestionForm()
    
    return render(request, 'exams/text_question_form.html', {
        'form': form,
        'exam_set': exam_set
    })

def edit_question(request, set_id, question_id):
    exam_set = get_object_or_404(ExamSet, id=set_id)
    question = get_object_or_404(Question, id=question_id, exam_set=exam_set)
    
    # Initialize form based on question type
    if question.question_type == 'MCQ':
        form_class = MCQQuestionForm
        template = 'exams/mcq_question_form.html'
        initial = {
            'choices': json.dumps(question.choices),
            'correct_choice': question.correct_choice
        }
    else:
        form_class = TextQuestionForm
        template = 'exams/text_question_form.html'
        initial = {}
    
    if request.method == 'POST':
        form = form_class(request.POST, instance=question)
        if form.is_valid():
            form.save()
            return redirect('exams:exam_set_detail', pk=exam_set.id)
    else:
        form = form_class(instance=question, initial=initial)
    
    return render(request, template, {
        'form': form,
        'exam_set': exam_set,
        'question': question
    })