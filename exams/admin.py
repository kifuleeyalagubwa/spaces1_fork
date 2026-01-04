from django.contrib import admin
from .models import ExamSet, Question, ExamAttempt, Answer, Grading, Correction, TextAssessmentSession, TextQuestionAssessment
from django.utils.html import format_html
from .constants import *

# exams/admin.py
from django.utils.html import format_html
from django.urls import reverse

class QuestionInline(admin.TabularInline):
    model = Question
    extra = 1
    fields = ('order', 'question_type', 'text', 'points', 'preview')
    readonly_fields = ('preview',)
    
    def preview(self, obj):
        if obj.question_type == 'MCQ':
            return format_html('<a href="{}?set_id={}">Edit MCQ</a>',
                reverse('admin:exams_question_change', args=[obj.id]),
                obj.exam_set.id
            )
        else:
            return format_html('<a href="{}?set_id={}">Edit Text</a>',
                reverse('admin:exams_question_change', args=[obj.id]),
                obj.exam_set.id
            )
    preview.short_description = 'Actions'




@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('short_text', 'exam_set_link', 'question_type', 'order', 'points')
    list_filter = ('question_type', 'exam_set__subject')
    search_fields = ('text', 'exam_set__title')
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Preselect related exam set to reduce queries
        return qs.select_related('exam_set')
    
    def exam_set_link(self, obj):
        return format_html('<a href="{}">{}</a>',
            reverse('admin:exams_examset_change', args=[obj.exam_set.id]),
            obj.exam_set.title
        )
    exam_set_link.short_description = 'Exam Set'
    exam_set_link.admin_order_field = 'exam_set__title'
    
    def short_text(self, obj):
        return obj.text[:50] + '...' if len(obj.text) > 50 else obj.text
    short_text.short_description = 'Question Text'
    
    def change_view(self, request, object_id, form_url='', extra_context=None):
        # Get set_id from query parameters
        set_id = request.GET.get('set_id')
        if set_id:
            # Add a link back to the exam set
            extra_context = extra_context or {}
            extra_context['back_url'] = reverse(
                'admin:exams_examset_change', 
                args=[set_id]
            )
            extra_context['back_label'] = 'Back to Exam Set'
        return super().change_view(request, object_id, form_url, extra_context)


# exams/admin.py
@admin.register(ExamSet)
class ExamSetAdmin(admin.ModelAdmin):
    inlines = [QuestionInline]
    list_display = ('title', 'creator', 'subject', 'set_type', 'question_count', 'is_active', 'created_at')
    list_filter = ('set_type', 'is_active', 'subject', 'creator')
    search_fields = ('title', 'description', 'creator__username')
    inlines = [QuestionInline]
    readonly_fields = ('uid', 'immutable_hash', 'created_at')  # Add created_at here
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'creator', 'subject', 'topic')
        }),
        ('Exam Settings', {
            'fields': ('set_type', 'credits_required', 'duration_minutes', 'is_active', 'reward_eligible')
        }),
        ('Metadata', {
            'fields': ('uid', 'immutable_hash', 'created_at')  # Keep it here but make readonly
        }),
    )
    
    def question_count(self, obj):
        return obj.questions.count()
    question_count.short_description = 'Questions'
    
    
    def save_model(self, request, obj, form, change):
        # First save to create primary key
        super().save_model(request, obj, form, change)
        
        # Now we can safely check questions
        if obj.questions.filter(question_type=QUESTION_TYPE_TEXT).exists():
            if obj.reward_eligible:
                obj.reward_eligible = False
                # Save only the reward_eligible field
                obj.save(update_fields=['reward_eligible'])



class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 0
    readonly_fields = ('question', 'mcq_answer', 'text_answer', 'is_correct', 'created_at')
    fields = ('question', 'mcq_answer', 'text_answer', 'is_correct', 'created_at')
    
    def has_add_permission(self, request, obj=None):
        return False

class GradingInline(admin.TabularInline):
    model = Grading
    extra = 0
    readonly_fields = ('question', 'is_correct', 'graded_by', 'graded_at', 'feedback')
    fields = ('question', 'is_correct', 'graded_by', 'graded_at', 'feedback')
    
    def has_add_permission(self, request, obj=None):
        return False

@admin.register(ExamAttempt)
class ExamAttemptAdmin(admin.ModelAdmin):
    list_display = ('user', 'exam_set', 'status', 'is_first_attempt', 'start_time', 'end_time', 'final_score')
    list_filter = ('status', 'is_first_attempt', 'exam_set__subject')
    search_fields = ('user__username', 'exam_set__title')
    readonly_fields = ( 'time_remaining', 'submission_hash', 'assessment_hash', 'browser_leaves')
    inlines = [AnswerInline, GradingInline]
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'exam_set', 'is_first_attempt')
        }),
        ('Timing', {
            'fields': ('start_time', 'end_time', 'time_remaining')
        }),
        ('Status', {
            'fields': ('status', 'browser_leaves', 'final_score', 'graded_at')
        }),
        ('Security & Blockchain', {
            'fields': ('submission_hash', 'assessment_hash'),
            'classes': ('collapse',)
        }),
    )
    
    def time_remaining(self, obj):
        return obj.time_remaining
    time_remaining.short_description = 'Time Remaining (sec)'

@admin.register(Correction)
class CorrectionAdmin(admin.ModelAdmin):
    list_display = ('question', 'exam_set', 'created_by', 'created_at')
    list_filter = ('exam_set__subject',)
    search_fields = ('explanation', 'question__text')
    readonly_fields = ('uid',)
    fields = ('exam_set', 'question', 'explanation', 'created_by', 'uid')

@admin.register(TextAssessmentSession)
class TextAssessmentSessionAdmin(admin.ModelAdmin):
    list_display = ('setter', 'attempt', 'is_completed', 'created_at')
    list_filter = ('is_completed',)
    search_fields = ('setter__username', 'attempt__exam_set__title')
    readonly_fields = ('immutable_hash', 'created_at', 'completed_at')
    fields = ('setter', 'attempt', 'is_completed', 'created_at', 'completed_at', 'immutable_hash')

@admin.register(TextQuestionAssessment)
class TextQuestionAssessmentAdmin(admin.ModelAdmin):
    list_display = ('session', 'question', 'score', 'assessed_at')
    list_filter = ('session__is_completed',)
    search_fields = ('question__text', 'feedback')
    readonly_fields = ('session', 'question', 'score', 'feedback', 'assessed_at')
    fields = ('session', 'question', 'score', 'feedback', 'assessed_at')
    
    def has_add_permission(self, request):
        return False

@admin.register(Grading)
class GradingAdmin(admin.ModelAdmin):
    list_display = ('attempt', 'question', 'is_correct', 'graded_by', 'graded_at')
    list_filter = ('is_correct',)
    search_fields = ('question__text', 'feedback')
    readonly_fields = ('attempt', 'question', 'graded_by', 'graded_at')
    fields = ('attempt', 'question', 'is_correct', 'feedback', 'graded_by', 'graded_at')
    
    def has_add_permission(self, request):
        return False

# exams/admin.py
class ExamSetFilter(admin.SimpleListFilter):
     title = 'Exam Set'
     parameter_name = 'exam_set'
     
     def lookups(self, request, model_admin):
         return ExamSet.objects.values_list('id', 'title')
     
     def queryset(self, request, queryset):
         if self.value():
             return queryset.filter(exam_set__id=self.value())        
        