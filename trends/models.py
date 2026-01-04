import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django_countries.fields import CountryField
from .constants import *
from django.db.models import Q
import re

class UUIDMixin(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    class Meta:
        abstract = True

class User(AbstractUser, UUIDMixin):
    is_verified = models.BooleanField(default=False)
    credits = models.PositiveIntegerField(default=0)
    
    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')
    
    @property
    def uid(self):
        return f"usr-{str(self.id)[:7]}"
    
  
    def save(self, *args, **kwargs):
        created = not self.pk
        super().save(*args, **kwargs)
        
        # Auto-verify superusers
        if self.is_superuser and not self.is_verified:
            self.is_verified = True
            # Save again to update is_verified
            super().save(update_fields=['is_verified'])

class EducationalSystem(UUIDMixin, models.Model):
    name = models.CharField(_('system name'), max_length=100, unique=True)
    system_type = models.CharField(
        _('system type'),
        max_length=20,
        choices=SystemType.CHOICES,
        default=SystemType.SECONDARY
    )
    description = models.TextField(_('description'), blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_systems'
    )
    is_approved = models.BooleanField(_('approved'), default=False)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    
    def __str__(self):
        return self.name
    
    @property
    def uid(self):
        return f"cur-{str(self.id)[:7]}"
        
# trends/models.py
class Institution(UUIDMixin, models.Model):
    # Basic Information
    name = models.CharField(_('name'), max_length=200)
    institution_type = models.CharField(
        _('institution type'),
        max_length=20,
        choices=InstitutionType.CHOICES,
        default=InstitutionType.EDUCATIONAL
    )
    description = models.TextField(_('description'), blank=True)
    
    # Contact Information
    email = models.EmailField(_('email'), blank=True)
    phone = models.CharField(_('phone'), max_length=20, blank=True)
    website = models.URLField(_('website'), blank=True)
    address = models.TextField(_('address'), blank=True)
    country = CountryField(blank=True)
    
    # Domain Configuration
    subdomain = models.CharField(_('subdomain'), max_length=50, unique=True, null=True, blank=True)
    custom_domain = models.CharField(_('custom domain'), max_length=100, unique=True, null=True, blank=True)
    
    # Status and Approval
    is_approved = models.BooleanField(_('approved'), default=False)
    is_active = models.BooleanField(_('active'), default=True)
    verified = models.BooleanField(_('verified'), default=False)
    
    # Administration
    admin = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='administered_institutions'
    )
    
    # Institution Branding
    logo = models.ImageField(upload_to='institution_logos/', null=True, blank=True)
    banner = models.ImageField(upload_to='institution_banners/', null=True, blank=True)
    primary_color = models.CharField(max_length=7, default='#8b0000')
    secondary_color = models.CharField(max_length=7, default='#f0f2f5')
    
    # Settings
    allow_user_registration = models.BooleanField(_('allow user registration'), default=True)
    require_domain_email = models.BooleanField(_('require domain email'), default=False)
    allowed_email_domains = models.CharField(_('allowed email domains'), max_length=500, blank=True)
    
    # Limits
    user_limit = models.PositiveIntegerField(_('user limit'), default=100)
    storage_quota_mb = models.PositiveIntegerField(_('storage quota (MB)'), default=1024)
    
    # Timestamps
    created_at = models.DateTimeField(_('created at'), auto_now_add=True,null=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    expiry_date = models.DateField(_('expiry date'), null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['subdomain'],
                name='unique_subdomain',
                condition=Q(subdomain__isnull=False)
            ),
            models.UniqueConstraint(
                fields=['custom_domain'],
                name='unique_custom_domain',
                condition=Q(custom_domain__isnull=False)
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.get_institution_type_display()})"

    
    # Add this method at the end of the class:
    def get_railway_domain(self):
        """Get the Railway domain for this institution"""
        railway_domain = os.environ.get('RAILWAY_STATIC_URL', '').replace('https://', '')
        if railway_domain and self.subdomain:
            return f"{self.subdomain}.{railway_domain}"
        elif self.custom_domain:
            return self.custom_domain
        elif self.subdomain:
            # Fallback for development
            return f"{self.subdomain}.127.0.0.1:8000"
        return None
    
    



    @property
    def uid(self):
        return f"ins-{str(self.id)[:7]}"

    def clean(self):
        if not self.subdomain and not self.custom_domain:
            raise ValidationError("Either subdomain or custom domain must be provided")
        
        if self.allowed_email_domains:
            domains = [domain.strip() for domain in self.allowed_email_domains.split(',')]
            for domain in domains:
                if not re.match(r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', domain):
                    raise ValidationError(f"Invalid domain format: {domain}")

    def save(self, *args, **kwargs):
        if not self.subdomain and not self.custom_domain:
            base_subdomain = re.sub(r'[^a-z0-9]', '', self.name.lower())[:20]
            counter = 1
            subdomain = base_subdomain
            while Institution.objects.filter(subdomain=subdomain).exists():
                subdomain = f"{base_subdomain}{counter}"
                counter += 1
            self.subdomain = subdomain
            
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        if self.custom_domain:
            return f"https://{self.custom_domain}"
        elif self.subdomain:
            return f"https://{self.subdomain}.127.0.0.1:8000"  # For development
        return None
        
class InstitutionScopedManager(models.Manager):
    def get_queryset(self):
        # For superusers or when institution scope is disabled, return all objects
        if hasattr(self.model, '_institution_scope_disabled'):
            return super().get_queryset()
            
        # For regular users, scope to their institution
        from .middleware import get_current_institution
        institution = get_current_institution()
        
        if institution:
            return super().get_queryset().filter(institution=institution)
        
        # If no institution in context, return empty queryset for safety
        return super().get_queryset().none()

# Abstract model for institution-scoped models
class InstitutionScopedModel(models.Model):
    institution = models.ForeignKey(
        Institution, 
        on_delete=models.CASCADE,
        related_name='%(class)s_objects'
    )
    
    objects = InstitutionScopedManager()
    
    class Meta:
        abstract = True
    
    def save(self, *args, **kwargs):
        # Auto-set institution if not provided
        from .middleware import get_current_institution
        if not self.institution_id:
            institution = get_current_institution()
            if institution:
                self.institution = institution
        
        super().save(*args, **kwargs)        
        

class EducationLevel(UUIDMixin, models.Model):
    system = models.ForeignKey(
        EducationalSystem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='levels'
    )
    institution_level = models.ForeignKey(
        Institution,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='custom_levels'
    )
    name = models.CharField(_('level name'), max_length=100)
    level_type = models.CharField(
        _('level type'),
        max_length=20,
        choices=LevelType.CHOICES,
        default=LevelType.GRADE
    )
    order = models.PositiveSmallIntegerField(_('order'), default=0)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_levels'
    )
    is_approved = models.BooleanField(_('approved'), default=False)
    
    class Meta:
        ordering = ['system', 'order']
    
    def __str__(self):
        return self.name
    
    @property
    def uid(self):
        return f"lvl-{str(self.id)[:7]}"
        
# trends/models.py - Update Profile model
class Profile(UUIDMixin, models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile'
    )
    
    # Role System - Keep both for compatibility
    role = models.CharField(  # Keep original role field for exams app
        max_length=20,
        choices=UserRole.CHOICES,
        default=UserRole.PARTICIPANT
    )
    global_role = models.CharField(
        max_length=20,
        choices=UserRole.CHOICES,
        default=UserRole.PARTICIPANT
    )
    institution_role = models.CharField(
        max_length=20,
        choices=UserRole.CHOICES,
        blank=True,
        null=True
    )
    
    # Institution Association
    institution = models.ForeignKey(
        Institution,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='members'
    )
    
    # Personal Information
    bio = models.TextField(_('bio'), blank=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    date_of_birth = models.DateField(null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = CountryField(blank=True)
    website = models.URLField(blank=True)
    
    # Institution-specific fields
    institution_name = models.CharField(max_length=200, blank=True)
    institution_logo = models.ImageField(upload_to='institution_logos/', blank=True, null=True)
    institution_description = models.TextField(blank=True)
    
    # Educational fields (for compatibility)
    education_system = models.ForeignKey(
        EducationalSystem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('education system')
    )
    education_level = models.ForeignKey(
        EducationLevel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('education level')
    )
    program = models.ForeignKey(
        'Program',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('degree program')
    )
    academic_year = models.ForeignKey(
        'Year',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('academic year')
    )
    
    created_at = models.DateTimeField(auto_now_add=True,null=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"

    @property
    def uid(self):
        return f"prf-{str(self.id)[:7]}"

    @property
    def effective_role(self):
        return self.institution_role or self.global_role or self.role

    def save(self, *args, **kwargs):
        # Auto-update role for backward compatibility
        if not self.role:
            self.role = self.effective_role
            
        # For institutional admins, update the institution info
        if self.role == UserRole.INSTITUTION_ADMIN and self.institution:
            self.institution_name = self.institution.name
            self.institution_logo = self.institution.logo
            self.institution_description = self.institution.description
            self.institution.save()
            
        super().save(*args, **kwargs)


class Subject(UUIDMixin, models.Model):
    education_level = models.ForeignKey(
        EducationLevel,  # Consistent naming
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subjects'
    )
    institution = models.ForeignKey(
        'Institution',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subjects'
    )
    name = models.CharField(_('subject name'), max_length=100)
    description = models.TextField(_('description'), blank=True)
    order = models.PositiveSmallIntegerField(_('order'), default=0)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_subjects'
    )
    is_approved = models.BooleanField(_('approved'), default=False)
    
    semester = models.ForeignKey(
        'Semester',  # String reference since Semester is defined later
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subjects'
    )
    
    class Meta:
        ordering = ['order']
    
    def __str__(self):
        return self.name
    
    @property
    def uid(self):
        return f"sub-{str(self.id)[:7]}"

class Topic(UUIDMixin, models.Model):
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name='topics'
    )
    name = models.CharField(_('topic name'), max_length=100)
    description = models.TextField(_('description'), blank=True)
    order = models.PositiveSmallIntegerField(_('order'), default=0)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_topics'
    )
    is_approved = models.BooleanField(_('approved'), default=False)
    
    class Meta:
        ordering = ['order']
    
    def __str__(self):
        return f"{self.subject.name} - {self.name}"
    
    @property
    def uid(self):
        return f"top-{str(self.id)[:7]}"

class SkillDomain(UUIDMixin, models.Model):
    name = models.CharField(_('domain name'), max_length=100, unique=True)
    description = models.TextField(_('description'), blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_skill_domains'
    )
    is_approved = models.BooleanField(_('approved'), default=False)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    
    def __str__(self):
        return self.name
    
    @property
    def uid(self):
        return f"skd-{str(self.id)[:7]}"

class SkillSubdomain(UUIDMixin, models.Model):
    domain = models.ForeignKey(
        SkillDomain,
        on_delete=models.CASCADE,
        related_name='subdomains'
    )
    name = models.CharField(_('subdomain name'), max_length=100)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_skill_subdomains'
    )
    is_approved = models.BooleanField(_('approved'), default=False)
    
    class Meta:
        unique_together = [('domain', 'name')]
    
    def __str__(self):
        return f"{self.domain.name} - {self.name}"
    
    @property
    def uid(self):
        return f"sks-{str(self.id)[:7]}"

# trends/models.py - Update Space model
class Space(UUIDMixin, models.Model):
    institution = models.ForeignKey(
        Institution,
        on_delete=models.CASCADE,
        related_name='spaces'
    )
    name = models.CharField(_('space name'), max_length=100)
    space_type = models.CharField(
        _('space type'),
        max_length=20,
        choices=SpaceType.CHOICES
    )
    description = models.TextField(_('description'), blank=True)
    
    # Virtual space details
    meeting_link = models.URLField(_('meeting link'), blank=True)
    access_code = models.CharField(_('access code'), max_length=50, blank=True)
    capacity = models.PositiveIntegerField(_('capacity'), default=10)
    
    # Availability for virtual spaces
    is_active = models.BooleanField(_('active'), default=True)
    available_from = models.TimeField(_('available from'), null=True, blank=True)
    available_to = models.TimeField(_('available to'), null=True, blank=True)
    
    # Supervisors/Moderators (can be multiple)
    supervisors = models.ManyToManyField(
        User,
        related_name='supervised_spaces',
        blank=True
    )
    
    # Tags for better organization
    tags = models.CharField(_('tags'), max_length=200, blank=True, 
                           help_text="Comma-separated tags for easy searching")
    
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_spaces'
    )
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        unique_together = ['institution', 'name']
        ordering = ['name']

    def __str__(self):
        return f"{self.name} - {self.institution.name}"

    @property
    def uid(self):
        return f"spc-{str(self.id)[:7]}"
    
    @property
    def space_type_description(self):
        return SpaceType.DESCRIPTIONS.get(self.space_type, "")
    
    def get_supervisors_display(self):
        return ", ".join([supervisor.get_full_name() or supervisor.username 
                         for supervisor in self.supervisors.all()])


# trends/models.py
class Trend(UUIDMixin, models.Model):
    institution = models.ForeignKey(
        Institution,
        on_delete=models.CASCADE,
        related_name='trends',null=True
    )
    space = models.ForeignKey(
        Space,
        on_delete=models.CASCADE,
        related_name='trends',
        null=True,
        blank=True
    )
    
    # Basic Information
    title = models.CharField(_('title'), max_length=200)
    description = models.TextField(_('description'), blank=True)
    trend_type = models.CharField(
        _('trend type'),
        max_length=20,
        choices=TrendType.CHOICES,default=True
    )
    
    # Scheduling
    start_time = models.DateTimeField(_('start time'),default=True)
    end_time = models.DateTimeField(_('end time'),null=True)
    is_recurring = models.BooleanField(_('recurring'), default=False)
    recurrence_pattern = models.CharField(_('recurrence pattern'), max_length=50, blank=True)
    
    # Participants
    organizer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='organized_trends',null=True
    )
    participants = models.ManyToManyField(
        User,
        related_name='participating_trends',
        blank=True
    )
    
    # Type-specific fields (generic JSON storage for flexibility)
    metadata = models.JSONField(_('metadata'), default=dict, blank=True)
    
    # Status
    is_active = models.BooleanField(_('active'), default=True)
    is_approved = models.BooleanField(_('approved'), default=True)  # Auto-approved for now
    
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        ordering = ['start_time']
        indexes = [
            models.Index(fields=['institution', 'start_time']),
            models.Index(fields=['space', 'start_time']),
        ]

    def __str__(self):
        return f"{self.title} - {self.start_time.strftime('%Y-%m-%d %H:%M')}"

    @property
    def uid(self):
        return f"trd-{str(self.id)[:7]}"

    def clean(self):
        if self.end_time <= self.start_time:
            raise ValidationError("End time must be after start time")
        
        # Check for space availability
        if self.space and self.pk is None:  # Only for new trends
            conflicting_trends = Trend.objects.filter(
                space=self.space,
                start_time__lt=self.end_time,
                end_time__gt=self.start_time,
                is_active=True
            ).exclude(pk=self.pk)
            
            if conflicting_trends.exists():
                raise ValidationError("Space is already booked for this time period")

    def duration(self):
        return self.end_time - self.start_time

    def is_ongoing(self):
        now = timezone.now()
        return self.start_time <= now <= self.end_time
        
class Program(UUIDMixin, models.Model):
    """University degree programs"""
    institution = models.ForeignKey(
        Institution,
        on_delete=models.CASCADE,
        related_name='programs'
    )
    name = models.CharField(_('program name'), max_length=200)
    duration = models.PositiveSmallIntegerField(
        _('duration in years'),
        default=4
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_programs'
    )
    is_approved = models.BooleanField(_('approved'), default=False)

    def __str__(self):
        return self.name

class Year(UUIDMixin, models.Model):
    """Academic year within a program"""
    program = models.ForeignKey(
        Program,
        on_delete=models.CASCADE,
        related_name='years'
    )
    name = models.CharField(_('year name'), max_length=50)
    order = models.PositiveSmallIntegerField(_('order'), default=1)

    class Meta:
        ordering = ['program', 'order']
        unique_together = [('program', 'name')]

    def __str__(self):
        return f"{self.program.name} - {self.name}"

class Semester(UUIDMixin, models.Model):
    """Semester within an academic year"""
    year = models.ForeignKey(
        Year,
        on_delete=models.CASCADE,
        related_name='semesters'
    )
    name = models.CharField(_('semester name'), max_length=50)
    order = models.PositiveSmallIntegerField(_('order'), default=1)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['year', 'order']
        unique_together = [('year', 'name')]

    def __str__(self):
        return f"{self.year} - {self.name}"        

        
        