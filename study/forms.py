from django import forms
from .models import StudyResource
from trends.models import Subject, Topic, EducationLevel, SkillDomain

class StudyResourceForm(forms.ModelForm):
    subjects = forms.ModelMultipleChoiceField(
        queryset=Subject.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )
    topics = forms.ModelMultipleChoiceField(
        queryset=Topic.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )
    education_level = forms.ModelChoiceField(
        queryset=EducationLevel.objects.all(),
        required=False
    )
    skill_domains = forms.ModelMultipleChoiceField(
        queryset=SkillDomain.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )
    
    class Meta:
        model = StudyResource
        fields = [
            'title', 'description', 'resource_type', 'access_level', 'access_cost',
            'file', 'thumbnail', 'transcript', 'duration', 'content',
            'subjects', 'topics', 'education_level', 'skill_domains'
        ]
        
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'content': forms.Textarea(attrs={'rows': 10}),
            'transcript': forms.Textarea(attrs={'rows': 5}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Set required=False for optional fields
        self.fields['file'].required = False
        self.fields['thumbnail'].required = False
        self.fields['transcript'].required = False
        self.fields['duration'].required = False
        self.fields['content'].required = False
        self.fields['access_cost'].required = False
        
        # Set initial values for new resources
        if self.instance.pk is None:
            self.fields['education_level'].queryset = EducationLevel.objects.filter(
                system__in=user.profile.education_system.all()
            )
    
    def clean(self):
        cleaned_data = super().clean()
        resource_type = cleaned_data.get('resource_type')
        thumbnail = cleaned_data.get('thumbnail')
        
        return cleaned_data
        content = cleaned_data.get('content')
        media_file = cleaned_data.get('file')
        
        # Validate text resources
        if resource_type == 'text' and not content:
            self.add_error('content', 'Content is required for text resources')
        
        # Validate media resources
        if resource_type in ['video', 'audio', 'pdf'] and not media_file:
            self.add_error('file', 'File upload is required for this resource type')
        
        # Validate premium resources
        access_level = cleaned_data.get('access_level')
        access_cost = cleaned_data.get('access_cost')
        
        if access_level == 'premium' and (access_cost is None or access_cost <= 0):
            self.add_error('access_cost', 'Premium resources must have a cost greater than 0')
        
        return cleaned_data