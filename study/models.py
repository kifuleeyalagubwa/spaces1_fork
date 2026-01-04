import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from trends.models import Subject, Topic, EducationLevel, SkillDomain
from trends.constants import AccessLevel
from .constants import ResourceType, UIDPrefix
import os
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from django.core.files import File
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from django.conf import settings

User = get_user_model()

class StudyResource(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(_('title'), max_length=200)
    description = models.TextField(_('description'))
    resource_type = models.CharField(
        _('resource type'),
        max_length=20,
        choices=ResourceType.CHOICES,
        default=ResourceType.TEXT
    )
    file = models.FileField(
        _('file'),
        upload_to='study_resources/',
        blank=True,
        null=True
    )
    content = models.TextField(_('content'), blank=True)
    creator = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='study_resources'
    )
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    subjects = models.ManyToManyField(Subject, blank=True)
    topics = models.ManyToManyField(Topic, blank=True)
    
    # New fields
    access_level = models.CharField(
        _('access level'),
        max_length=20,
        choices=AccessLevel.ACCESS_LEVEL_CHOICES,
        default=AccessLevel.PUBLIC
    )
    access_cost = models.PositiveIntegerField(
        _('access cost'),
        default=0
    )
    education_level = models.ForeignKey(
        EducationLevel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('education level')
    )
    skill_domains = models.ManyToManyField(
        SkillDomain,
        blank=True,
        verbose_name=_('skill domains')
    )
    thumbnail = models.ImageField(
        _('thumbnail'),
        upload_to='resource_thumbnails/',
        blank=True,
        null=True
    )
    transcript = models.TextField(
        _('transcript'),
        blank=True
    )
    duration = models.PositiveIntegerField(
        _('duration (seconds)'),
        blank=True,
        null=True
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('study resource')
        verbose_name_plural = _('study resources')

    def __str__(self):
        return self.title

    @property
    def uid(self):
        return f"{UIDPrefix.RESOURCE}-{str(self.id)[:7]}"
    
    def get_duration_display(self):
        """Convert seconds to minutes:seconds format"""
        if not self.duration:
            return "N/A"
        minutes = self.duration // 60
        seconds = self.duration % 60
        return f"{minutes}:{seconds:02d}"
        
    
    
    def save(self, *args, **kwargs):
        # Generate thumbnail if it's a video and none was provided
        if self.resource_type == ResourceType.VIDEO and not self.thumbnail:
            self.generate_thumbnail()
        super().save(*args, **kwargs)

    def generate_thumbnail(self):
        """Generate a thumbnail with the video title initials"""
        # Get initials from title
        words = [word for word in self.title.split() if word]
        
        if not words:
            initials = "VD"  # Default for empty titles
        elif len(words) == 1:
            initials = words[0][:2].upper()
        else:
            initials = words[0][0].upper() + words[-1][0].upper()
        # Create image with initials
        img_size = (400, 300)
        background_color = (41, 128, 185)  # Nice blue
        text_color = (255, 255, 255)       # White
        
        img = Image.new('RGB', img_size, background_color)
        draw = ImageDraw.Draw(img)
        
        try:
            # Try to load a font
            font_path = os.path.join(settings.BASE_DIR, 'static', 'fonts', 'Roboto-Bold.ttf')
            font = ImageFont.truetype(font_path, 120)
        except IOError:
            # Fallback to default font
            font = ImageFont.load_default()
        
        # Center the text
        
        
        # Save to BytesIO buffer
        buffer = BytesIO()
        img.save(buffer, format='JPEG')
        buffer.seek(0)
        
        # Create filename
        filename = f"{slugify(self.title)}-thumbnail.jpg"
        
        # Save to thumbnail field
        self.thumbnail.save(filename, File(buffer), save=False)
        
    def clean(self):
        """Validate that videos have thumbnails"""
        if self.resource_type == ResourceType.VIDEO and not self.thumbnail:
            # Don't raise error here - we'll generate one automatically
            pass    

class ResourceCategory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_('name'), max_length=100)
    description = models.TextField(_('description'), blank=True)
    resources = models.ManyToManyField(StudyResource, blank=True)
    
    class Meta:
        verbose_name = _('resource category')
        verbose_name_plural = _('resource categories')
    
    def __str__(self):
        return self.name
    
    @property
    def uid(self):
        return f"{UIDPrefix.CATEGORY}-{str(self.id)[:7]}"

class ResourceBookmark(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    resource = models.ForeignKey(StudyResource, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'resource')
        verbose_name = _('bookmark')
        verbose_name_plural = _('bookmarks')
    
    def __str__(self):
        return f"{self.user.username} - {self.resource.title}"
    
    @property
    def uid(self):
        return f"{UIDPrefix.BOOKMARK}-{str(self.id)[:7]}"