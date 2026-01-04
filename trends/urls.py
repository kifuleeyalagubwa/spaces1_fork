from django.urls import path
from . import views

urlpatterns = [
    # Authentication
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('welcome/', views.welcome_view, name='welcome'),
    
    # User Profile
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    
    # Dashboard
    path('', views.dashboard_view, name='dashboard'),
    
    # Content Creation
    path('system/create/', views.create_educational_system, name='system_create'),
    path('level/create/', views.create_education_level, name='create_level'),
    path('subject/create/', views.create_subject, name='subject_create'),
    path('topic/create/', views.create_topic, name='create_topic'),
    path('domain/create/', views.create_skill_domain, name='create_domain'),
    path('institution/create/', views.create_institution, name='create_institution'),
    path('trend/create/', views.create_trend, name='create_trend'),
    
    # AJAX Loaders
    path('ajax/load-levels/', views.load_education_levels, name='ajax_load_levels'),
    path('ajax/load-programs/', views.load_programs, name='ajax_load_programs'),
    path('ajax/load-years/', views.load_years, name='ajax_load_years'),
    
    # Admin Views
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/users/', views.admin_user_list, name='admin_user_list'),
    path('admin/users/<uuid:pk>/', views.admin_user_detail, name='admin_user_detail'),
    path('admin/content-review/', views.content_review_dashboard, name='content_review'),
    path('admin/approve/<str:model>/<uuid:pk>/', views.approve_item, name='approve_item'),
    path('admin/reject/<str:model>/<uuid:pk>/', views.reject_item, name='reject_item'),
    path('admin/metrics/', views.system_metrics, name='system_metrics'),

    path('institution/register/', views.register_institution, name='register_institution'),
    path('institution/dashboard/', views.institution_dashboard, name='institution_dashboard'),

    path('institution/level/create/', views.create_institution_level, name='create_institution_level'),
    path('institution/subject/create/', views.create_institution_subject, name='create_institution_subject'),
    path('institution/topic/create/', views.create_institution_topic, name='create_institution_topic'),
    path('institution/trend/create/', views.create_institution_trend, name='create_institution_trend'),
    
    path('test-registration/', views.test_institution_registration, name='test_registration'),
    path('subdomain-test/', views.subdomain_test, name='subdomain_test'),
    
    # Add these placeholder URLs for the dashboard links
    
    path('users/manage/', views.user_management, name='user_management'),
    path('settings/', views.institution_settings, name='institution_settings'),
    
    
    # Space URLs
    path('spaces/', views.space_list, name='space_list'),
    path('spaces/create/', views.space_create, name='space_create'),
    path('spaces/<uuid:pk>/', views.space_detail, name='space_detail'),
    path('spaces/<uuid:pk>/edit/', views.space_edit, name='space_edit'),
    
    # Trend URLs
    path('trends/', views.trend_list, name='trend_list'),
    path('trends/create/', views.trend_create, name='trend_create'),
    path('trends/calendar/', views.trend_calendar, name='trend_calendar'),
    
    path('institution/switch/', views.institution_switch, name='institution_switch'),
    path('institution/select/<uuid:institution_id>/', views.select_institution, name='select_institution'),
]