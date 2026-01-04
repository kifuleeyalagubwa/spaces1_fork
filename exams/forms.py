from django import forms
from .models import ExamSet, Question, Answer, Grading, Correction
from trends.models import Subject, Topic
from .constants import QUESTION_TYPE_MCQ, QUESTION_TYPE_TEXT,EXAM_SET_TYPE_PREMIUM
import json


class ExamSetForm(forms.ModelForm):
    class Meta:
        model = ExamSet
        fields = ['title', 'description', 'subject', 'topic', 'set_type', 
                  'credits_required', 'duration_minutes', 'is_active', 'reward_eligible']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make credits_required not required initially
        self.fields['credits_required'].required = False
    
    def clean(self):
        cleaned_data = super().clean()
        set_type = cleaned_data.get('set_type')
        credits_required = cleaned_data.get('credits_required', 0)
        
        if set_type == EXAM_SET_TYPE_PREMIUM:
            if credits_required is None or credits_required <= 0:
                self.add_error('credits_required', 'Premium exams require a positive credit value.')
        else:
            # Set to 0 for non-premium exams
            cleaned_data['credits_required'] = 0
            
        return cleaned_data

class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ['text', 'order', 'points', 'question_type']
        widgets = {
            'text': forms.Textarea(attrs={'rows': 3}),
        }





class MCQQuestionForm(forms.ModelForm):
    choices = forms.CharField(widget=forms.HiddenInput())
    correct_choice = forms.CharField()
    
    class Meta:
        model = Question
        fields = ['text', 'points', 'order', 'choices', 'correct_choice']
        widgets = {
            'text': forms.Textarea(attrs={'rows': 3}),
        }
        labels = {
            'text': 'Question Text',
            'points': 'Points',
            'order': 'Question Order',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.choices:
            self.initial['choices'] = json.dumps(self.instance.choices)
            self.initial['correct_choice'] = self.instance.correct_choice
        self.fields['correct_choice'].required = False  # Will validate in clean
    
    def clean_choices(self):
        data = self.cleaned_data['choices']
        try:
            choices = json.loads(data)
            if not isinstance(choices, list):
                raise forms.ValidationError("Choices must be a list")
            if len(choices) < 2:
                raise forms.ValidationError("At least two choices are required")
            for choice in choices:
                if 'letter' not in choice or 'text' not in choice:
                    raise forms.ValidationError("Each choice must have 'letter' and 'text' properties")
            return choices
        except json.JSONDecodeError:
            raise forms.ValidationError("Invalid choices format")
    
    def clean_correct_choice(self):
        data = self.cleaned_data['correct_choice']
        choices = self.cleaned_data.get('choices', [])
        if choices and not data:
            raise forms.ValidationError("Please select the correct answer")
        if choices and data:
            choice_letters = [c['letter'] for c in choices]
            if data not in choice_letters:
                raise forms.ValidationError("Correct choice must be one of the provided options")
        return data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.question_type = QUESTION_TYPE_MCQ
        instance.choices = self.cleaned_data['choices']
        instance.correct_choice = self.cleaned_data['correct_choice']
        if commit:
            instance.save()
        return instance

class TextQuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ['text', 'points', 'order', 'reference_answer', 'max_length']
        widgets = {
            'reference_answer': forms.Textarea(attrs={'rows': 4}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        # Text questions require max_length
        if not cleaned_data.get('max_length'):
            self.add_error('max_length', "This field is required for text questions")
        return cleaned_data

class AnswerForm(forms.ModelForm):
    class Meta:
        model = Answer
        fields = ['mcq_answer', 'text_answer']
    
    def __init__(self, *args, **kwargs):
        self.question = kwargs.pop('question', None)
        super().__init__(*args, **kwargs)
        
        if self.question:
            if self.question.question_type == QUESTION_TYPE_MCQ:
                self.fields['mcq_answer'].required = True
                self.fields['text_answer'].widget = forms.HiddenInput()
                
                # Set choices for MCQ
                choices = [(choice['letter'], choice['text']) for choice in self.question.choices]
                self.fields['mcq_answer'].widget = forms.RadioSelect(choices=choices)
            else:
                self.fields['text_answer'].required = True
                self.fields['mcq_answer'].widget = forms.HiddenInput()
                self.fields['text_answer'].widget = forms.Textarea(attrs={
                    'rows': 3,
                    'maxlength': self.question.max_length
                })

class GradingForm(forms.ModelForm):
    class Meta:
        model = Grading
        fields = ['is_correct', 'feedback']
        widgets = {
            'is_correct': forms.RadioSelect(choices=[(True, '✓ Correct'), (False, '✗ Incorrect')]),
            'feedback': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Optional feedback...'}),
        }

class CorrectionForm(forms.ModelForm):
    class Meta:
        model = Correction
        fields = ['explanation']
        widgets = {
            'explanation': forms.Textarea(attrs={'rows': 4}),
        }