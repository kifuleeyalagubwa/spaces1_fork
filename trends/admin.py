# trends/admin.py - Complete fixed version
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib import messages
from .models import (
    User, Profile, EducationalSystem, EducationLevel,
    Subject, Topic, SkillDomain, SkillSubdomain, 
    Institution, Trend, Space
)
from .constants import UserRole

# Approval actions
def approve_items(modeladmin, request, queryset):
    updated = queryset.update(is_approved=True)
    modeladmin.message_user(
        request, 
        f"{updated} items approved successfully!", 
        messages.SUCCESS
    )
approve_items.short_description = "Approve selected items"

def verify_users(modeladmin, request, queryset):
    updated = queryset.update(is_verified=True)
    modeladmin.message_user(
        request, 
        f"{updated} users verified successfully!", 
        messages.SUCCESS
    )
verify_users.short_description = "Verify selected users"

class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Profile'
    fk_name = 'user'
    fields = ['role', 'global_role', 'institution_role', 'institution', 'profile_picture']
    readonly_fields = []

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'uid', 'is_verified', 'credits', 'is_staff')
    list_filter = ('is_staff', 'is_superuser', 'is_verified')
    search_fields = ('username', 'email', 'uid')
    actions = [verify_users]
    list_display_links = ('username', 'email', 'uid')
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
        ('Custom Fields', {'fields': ('is_verified', 'credits')}),
    )
    
    inlines = [ProfileInline]
    
    def get_inline_instances(self, request, obj=None):
        if not obj:
            return list()
        return super().get_inline_instances(request, obj)

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'uid', 'role', 'global_role', 'institution_role', 'institution')
    list_filter = ('role', 'global_role', 'institution_role', 'country')
    search_fields = ('user__username', 'institution__name', 'uid')
    list_editable = ('role', 'global_role', 'institution_role')
    
    fieldsets = (
        (None, {
            'fields': ('user', 'role', 'global_role', 'institution_role', 'institution')
        }),
        ('Personal Information', {
            'fields': (
                'profile_picture', 'date_of_birth', 'phone',
                'address', 'city', 'country', 'website', 'bio'
            )
        }),
        ('Institution Information', {
            'fields': ('institution_name', 'institution_logo', 'institution_description'),
            'classes': ('collapse',)
        }),
        ('Educational Information', {
            'fields': ('education_system', 'education_level', 'program', 'academic_year'),
            'classes': ('collapse',)
        }),
    )

@admin.register(Institution)
class InstitutionAdmin(admin.ModelAdmin):
    list_display = ('name', 'institution_type', 'subdomain', 'admin', 'verified', 'is_approved', 'is_active')
    list_editable = ('verified', 'is_approved', 'is_active')
    list_filter = ('institution_type', 'verified', 'is_approved', 'is_active')
    search_fields = ('name', 'admin__username', 'subdomain')
    actions = [approve_items]
    raw_id_fields = ['admin']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'institution_type', 'admin', 'verified', 'is_approved', 'is_active')
        }),
        ('Domain Settings', {
            'fields': ('subdomain', 'custom_domain'),
        }),
        ('Contact Information', {
            'fields': ('description', 'email', 'phone', 'website', 'address', 'country'),
        }),
        ('Branding', {
            'fields': ('logo', 'banner', 'primary_color', 'secondary_color'),
            'classes': ('collapse',)
        }),
        ('Settings', {
            'fields': ('allow_user_registration', 'require_domain_email', 'allowed_email_domains'),
            'classes': ('collapse',)
        }),
        ('Limits', {
            'fields': ('user_limit', 'storage_quota_mb', 'expiry_date'),
            'classes': ('collapse',)
        }),
    )

@admin.register(Space)
class SpaceAdmin(admin.ModelAdmin):
    list_display = ('name', 'space_type', 'institution', 'capacity', 'is_active', 'created_at')
    list_filter = ('space_type', 'institution', 'is_active')
    search_fields = ('name', 'institution__name', 'meeting_link', 'tags')
    raw_id_fields = ('institution', 'created_by')
    filter_horizontal = ('supervisors',)
    
    fieldsets = (
        (None, {
            'fields': ('institution', 'name', 'space_type', 'description')
        }),
        ('Virtual Space Details', {
            'fields': ('meeting_link', 'access_code', 'capacity', 'tags')
        }),
        ('Availability', {
            'fields': ('is_active', 'available_from', 'available_to')
        }),
        ('Management', {
            'fields': ('supervisors', 'created_by')
        }),
    )

@admin.register(Trend)
class TrendAdmin(admin.ModelAdmin):
    list_display = ('title', 'trend_type', 'institution', 'space', 'start_time', 'is_active')
    list_filter = ('trend_type', 'institution', 'is_active')
    search_fields = ('title', 'institution__name', 'organizer__username')
    raw_id_fields = ('institution', 'space', 'organizer')
    
    fieldsets = (
        (None, {
            'fields': ('title', 'description', 'trend_type', 'organizer', 'institution', 'is_active')
        }),
        ('Scheduling', {
            'fields': ('start_time', 'end_time', 'space', 'is_recurring', 'recurrence_pattern'),
        }),
        ('Participants', {
            'fields': ('participants',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at')

# Keep other admin registrations as they are
@admin.register(EducationalSystem)
class EducationalSystemAdmin(admin.ModelAdmin):
    list_display = ('name', 'system_type', 'uid', 'created_by', 'is_approved')
    list_editable = ('is_approved',)
    list_filter = ('system_type', 'is_approved')
    search_fields = ('name', 'created_by__username', 'uid')
    actions = [approve_items]
    raw_id_fields = ('created_by',)

@admin.register(EducationLevel)
class EducationLevelAdmin(admin.ModelAdmin):
    list_display = ('name', 'level_type', 'uid', 'system', 'order', 'is_approved')
    list_editable = ('is_approved',)
    list_filter = ('system', 'level_type', 'is_approved')
    search_fields = ('name', 'system__name', 'uid')
    actions = [approve_items]
    raw_id_fields = ('created_by', 'parent', 'system')
    list_select_related = ('system', 'parent')

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'uid', 'education_level', 'institution', 'order', 'is_approved')
    list_editable = ('is_approved',)
    list_filter = ('education_level', 'institution', 'is_approved')
    search_fields = ('name', 'education_level__name', 'uid')
    actions = [approve_items]
    raw_id_fields = ('created_by', 'education_level', 'institution')
    list_select_related = ('education_level', 'institution')

@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ('name', 'uid', 'subject', 'order', 'is_approved')
    list_editable = ('is_approved',)
    list_filter = ('subject', 'is_approved')
    search_fields = ('name', 'subject__name', 'uid')
    actions = [approve_items]
    raw_id_fields = ('created_by',)
    list_select_related = ('subject',)

@admin.register(SkillDomain)
class SkillDomainAdmin(admin.ModelAdmin):
    list_display = ('name', 'uid', 'created_by', 'is_approved')
    list_editable = ('is_approved',)
    list_filter = ('is_approved',)
    search_fields = ('name', 'created_by__username', 'uid')
    actions = [approve_items]
    raw_id_fields = ('created_by',)

@admin.register(SkillSubdomain)
class SkillSubdomainAdmin(admin.ModelAdmin):
    list_display = ('name', 'uid', 'domain', 'is_approved')
    list_editable = ('is_approved',)
    list_filter = ('domain', 'is_approved')
    search_fields = ('name', 'domain__name', 'uid')
    actions = [approve_items]
    raw_id_fields = ('created_by',)
    list_select_related = ('domain',)