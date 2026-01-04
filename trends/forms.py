from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import *
from django_countries.widgets import CountrySelectWidget
from .constants import UserRole, AccessLevel  # Import constants
import re
from django.core.exceptions import ValidationError
from .constants import *



class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)
    
    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']


# trends/forms.py - Update ProfileForm with all fields
class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = [
            'role', 'global_role', 'institution_role', 'institution',
            'bio', 'profile_picture', 'date_of_birth', 'phone',
            'address', 'city', 'country', 'website',
            'institution_name', 'institution_logo', 'institution_description',
            'education_system', 'education_level', 'program', 'academic_year'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'bio': forms.Textarea(attrs={'rows': 4}),
            'address': forms.Textarea(attrs={'rows': 3}),
            'institution_description': forms.Textarea(attrs={'rows': 3}),
            'country': CountrySelectWidget(),
            'role': forms.Select(attrs={'class': 'form-select'}),
            'global_role': forms.Select(attrs={'class': 'form-select'}),
            'institution_role': forms.Select(attrs={'class': 'form-select'}),
            'institution': forms.Select(attrs={'class': 'form-select'}),
            'education_system': forms.Select(attrs={'class': 'form-select'}),
            'education_level': forms.Select(attrs={'class': 'form-select'}),
            'program': forms.Select(attrs={'class': 'form-select'}),
            'academic_year': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set institution choices
        self.fields['institution'].queryset = Institution.objects.filter(
            is_active=True, 
            is_approved=True
        )
        
        # Set education system choices
        self.fields['education_system'].queryset = EducationalSystem.objects.filter(is_approved=True)
        
        # Make institution field required only if institution_role is set
        if not self.instance.institution_role:
            self.fields['institution'].required = False
        
        # Limit role choices based on user permissions
        if not self.instance.user.is_superuser:
            # Remove admin roles for non-superusers
            admin_roles = [UserRole.ADMIN]
            self.fields['role'].choices = [
                choice for choice in UserRole.CHOICES 
                if choice[0] not in admin_roles
            ]
            self.fields['global_role'].choices = [
                choice for choice in UserRole.CHOICES 
                if choice[0] not in admin_roles
            ]
            self.fields['institution_role'].choices = [
                choice for choice in UserRole.CHOICES 
                if choice[0] not in admin_roles
            ]


class LoginForm(forms.Form):
    username = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput)

class EducationalSystemForm(forms.ModelForm):
    class Meta:
        model = EducationalSystem
        fields = ['name', 'system_type', 'description']  # Added system_type
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'system_type': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.created_by = self.user
        if commit: 
            instance.save()
        return instance



class SkillDomainForm(forms.ModelForm):
    class Meta:
        model = SkillDomain
        fields = ['name', 'description']
        widgets = {'description': forms.Textarea(attrs={'rows': 3})}
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.created_by = self.user
        if commit: 
            instance.save()
        return instance

# trends/forms.py - Fix the InstitutionForm
class InstitutionForm(forms.ModelForm):
    class Meta:
        model = Institution
        fields = ['name', 'description', 'website']  # Remove 'curriculum'
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        # Remove curriculum-related code since the field doesn't exist
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.admin = self.user
        if commit: 
            instance.save()
        return instance        
# trends/forms.py
# trends/forms.py - Fix the InstitutionRegistrationForm
class InstitutionRegistrationForm(forms.ModelForm):
    admin_first_name = forms.CharField(max_length=30, required=True)
    admin_last_name = forms.CharField(max_length=30, required=True)
    admin_email = forms.EmailField(required=True)
    password = forms.CharField(widget=forms.PasswordInput, required=True)
    password_confirm = forms.CharField(widget=forms.PasswordInput, required=True)
    agree_to_terms = forms.BooleanField(required=True)
    
    class Meta:
        model = Institution
        fields = [
            'institution_type', 'name', 'subdomain', 'email', 'phone', 
            'website', 'address', 'country', 'description'
        ]  # Remove 'curriculum' and 'custom_curriculum'
        widgets = {
            'institution_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'rows': 3}),
            'address': forms.Textarea(attrs={'rows': 2}),
            'country': CountrySelectWidget(),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove curriculum-related code
        self.fields['subdomain'].help_text = 'Will be used for your institution URL: https://yoursubdomain.127.0.0.1:8000'
    
    def clean_subdomain(self):
        subdomain = self.cleaned_data.get('subdomain', '').lower()
        if not subdomain:
            return subdomain
            
        if not re.match(r'^[a-z0-9-]+$', subdomain):
            raise ValidationError("Subdomain can only contain lowercase letters, numbers, and hyphens.")
        
        if Institution.objects.filter(subdomain=subdomain).exists():
            raise ValidationError("This subdomain is already taken.")
            
        return subdomain
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')
        
        if password and password_confirm and password != password_confirm:
            self.add_error('password_confirm', "Passwords do not match")
            
        return cleaned_data
    
    
        
    # trends/forms.py - Fix the InstitutionRegistrationForm save method
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Create or get admin user
        admin_email = self.cleaned_data['admin_email']
        admin_user, created = User.objects.get_or_create(
            email=admin_email,
            defaults={
                'username': admin_email,
                'first_name': self.cleaned_data['admin_first_name'],
                'last_name': self.cleaned_data['admin_last_name'],
                'is_verified': True
            }
        )
        
        if created:
            admin_user.set_password(self.cleaned_data['password'])
            admin_user.save()
        else:
            # User already exists, update password if provided
            if self.cleaned_data['password']:
                admin_user.set_password(self.cleaned_data['password'])
                admin_user.save()
        
        instance.admin = admin_user
        
        if commit:
            instance.save()
            
            # Get or create profile (don't create if already exists)
            profile, profile_created = Profile.objects.get_or_create(
                user=admin_user,
                defaults={
                    'global_role': 'participant',
                    'institution_role': 'institution_admin',
                    'institution': instance
                }
            )
            
            if not profile_created:
                # Update existing profile
                profile.institution_role = 'institution_admin'
                profile.institution = instance
                profile.save()
        
        return instance        
        
        


class EducationLevelForm(forms.ModelForm):
    class Meta:
        model = EducationLevel
        fields = ['system', 'level_type', 'name', 'order', 'parent']
        widgets = {
            'system': forms.Select(attrs={'class': 'form-select'}),
            'parent': forms.Select(attrs={'class': 'form-select'}),
            'level_type': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.institution = kwargs.pop('institution', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Hide system field for institutional curriculum
        if self.institution and self.institution.custom_curriculum:
            self.fields['system'].widget = forms.HiddenInput()
            self.fields['system'].required = False
            self.fields['system'].queryset = EducationalSystem.objects.none()
        else:
            self.fields['system'].queryset = EducationalSystem.objects.filter(is_approved=True)
        
        # Dynamic filtering for parent levels
        if 'system' in self.data:
            system_id = self.data.get('system')
            self.fields['parent'].queryset = EducationLevel.objects.filter(
                system_id=system_id, is_approved=True
            )
        elif self.instance.pk and self.instance.system:
            self.fields['parent'].queryset = self.instance.system.levels.filter(
                is_approved=True
            )
        else:
            self.fields['parent'].queryset = EducationLevel.objects.none()
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.created_by = self.user
        
        # Link to institution for custom curriculum
        if self.institution and self.institution.custom_curriculum:
            instance.institution_level = self.institution
        
        if commit: 
            instance.save()
        return instance

class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['education_level', 'institution', 'name', 'description', 'order']
        widgets = {
            'education_level': forms.Select(attrs={'class': 'form-select'}),
            'institution': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        self.institution = kwargs.pop('institution', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if self.institution:
            self.fields['institution'].initial = self.institution
            self.fields['institution'].widget = forms.HiddenInput()
            self.fields['education_level'].queryset = EducationLevel.objects.filter(
                Q(system=self.institution.curriculum) | 
                Q(institution_level=self.institution)
            )
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.created_by = self.user
        if commit: 
            instance.save()
        return instance

class TopicForm(forms.ModelForm):
    class Meta:
        model = Topic
        fields = ['subject', 'name', 'description', 'order']
        widgets = {
            'subject': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        self.institution = kwargs.pop('institution', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if self.institution:
            self.fields['subject'].queryset = Subject.objects.filter(
                institution=self.institution
            )
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.created_by = self.user
        if commit: 
            instance.save()
        return instance

# trends/forms.py - Fix the TrendForm
class TrendForm(forms.ModelForm):
    class Meta:
        model = Trend
        fields = [
            'title', 'description', 'trend_type', 'space',
            'start_time', 'end_time', 'is_recurring', 'recurrence_pattern'
        ]  # Only use fields that exist in the Trend model
        widgets = {
            'trend_type': forms.Select(attrs={'class': 'form-select'}),
            'space': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'rows': 4}),
            'start_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'end_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.institution = kwargs.pop('institution', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filter spaces by institution
        if self.institution:
            self.fields['space'].queryset = Space.objects.filter(
                institution=self.institution
            )
        else:
            self.fields['space'].queryset = Space.objects.none()
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.organizer = self.user
        if self.institution:
            instance.institution = self.institution
            
        if commit:
            instance.save()
        return instance
        
# trends/forms.py - Update SpaceForm
class SpaceForm(forms.ModelForm):
    class Meta:
        model = Space
        fields = [
            'name', 'space_type', 'description', 'meeting_link', 'access_code',
            'capacity', 'available_from', 'available_to', 'supervisors', 'tags'
        ]
        widgets = {
            'space_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'rows': 3}),
            'available_from': forms.TimeInput(attrs={'type': 'time'}),
            'available_to': forms.TimeInput(attrs={'type': 'time'}),
            'supervisors': forms.SelectMultiple(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.institution = kwargs.pop('institution', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if self.institution:
            # Filter supervisors to institution members
            self.fields['supervisors'].queryset = User.objects.filter(
                profile__institution=self.institution
            )
            
            # Add space type descriptions as help text
            for value, label in SpaceType.CHOICES:
                self.fields['space_type'].help_text = f"<div class='space-type-help'>{SpaceType.DESCRIPTIONS[value]}</div>"
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.institution:
            instance.institution = self.institution
        if self.user:
            instance.created_by = self.user
        if commit:
            instance.save()
            self.save_m2m()  # Save many-to-many for supervisors
        return instance