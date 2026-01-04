from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import *
from .models import *
from .constants import UserRole  # Import constants

from django.http import JsonResponse,HttpResponse
from .models import EducationLevel, Program, Year
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Q
from django.db.models.functions import TruncDay, TruncMonth
from django.utils import timezone
from datetime import timedelta
from django.core.mail import send_mail
from django.conf import settings
from .forms import InstitutionRegistrationForm



@staff_member_required
def system_metrics(request):
    # 1. User Growth Metrics (Last 30 days)
    today = timezone.now().date()
    thirty_days_ago = today - timedelta(days=30)
    
    user_growth = (
        User.objects
        .filter(date_joined__date__gte=thirty_days_ago)
        .annotate(date=TruncDay('date_joined'))
        .values('date')
        .annotate(count=Count('id'))
        .order_by('date')
    )
    
    # Prepare data for user growth chart
    user_growth_dates = [entry['date'].strftime("%Y-%m-%d") for entry in user_growth]
    user_growth_counts = [entry['count'] for entry in user_growth]
    
    # Fill in missing days with zero counts
    full_dates = []
    full_counts = []
    current_date = thirty_days_ago
    while current_date <= today:
        date_str = current_date.strftime("%Y-%m-%d")
        if date_str in user_growth_dates:
            idx = user_growth_dates.index(date_str)
            full_counts.append(user_growth_counts[idx])
        else:
            full_counts.append(0)
        full_dates.append(date_str)
        current_date += timedelta(days=1)
    
    # 2. Educational System Distribution
    system_distribution = (
        EducationalSystem.objects
        .filter(is_approved=True)
        .annotate(
            level_count=Count('levels', distinct=True),
            subject_count=Count('levels__subjects', distinct=True),
            trend_count=Count('levels__academic_trends', distinct=True)
        )
        .order_by('-trend_count')[:10]  # Top 10 systems
    )
    
    # Prepare data for system distribution chart
    system_names = [system.name for system in system_distribution]
    level_counts = [system.level_count for system in system_distribution]
    subject_counts = [system.subject_count for system in system_distribution]
    trend_counts = [system.trend_count for system in system_distribution]
    
    # 3. Trend Type Distribution
    trend_types = (
        Trend.objects
        .filter(is_approved=True)
        .values('space_type')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    
    # Map space type codes to human-readable names
    space_type_names = {
        'study': 'Study Space',
        'interview': 'Interview Space',
        'meeting': 'Meeting Space'
    }
    
    trend_type_labels = [space_type_names[entry['space_type']] for entry in trend_types]
    trend_type_counts = [entry['count'] for entry in trend_types]
    
    # 4. User Role Distribution
    role_distribution = (
        Profile.objects
        .values('role')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    
    role_names = {
        'participant': 'Participant',
        'setter': 'Setter',
        'institution': 'Institution',
        'admin': 'Admin'
    }
    
    role_labels = [role_names[entry['role']] for entry in role_distribution]
    role_counts = [entry['count'] for entry in role_distribution]
    
    # 5. Active Content Metrics
    active_trends = Trend.objects.filter(is_approved=True).count()
    active_systems = EducationalSystem.objects.filter(is_approved=True).count()
    active_levels = EducationLevel.objects.filter(is_approved=True).count()
    active_subjects = Subject.objects.filter(is_approved=True).count()
    
    # 6. Recent Growth (Last 7 days)
    week_ago = today - timedelta(days=7)
    recent_users = User.objects.filter(date_joined__date__gte=week_ago).count()
    recent_trends = Trend.objects.filter(created_at__date__gte=week_ago).count()
    
    return render(request, 'trend/system_metrics.html', {
        # Chart data
        'user_growth_dates': full_dates,
        'user_growth_counts': full_counts,
        'system_names': system_names,
        'level_counts': level_counts,
        'subject_counts': subject_counts,
        'trend_counts': trend_counts,
        'trend_type_labels': trend_type_labels,
        'trend_type_counts': trend_type_counts,
        'role_labels': role_labels,
        'role_counts': role_counts,
        
        # Metric cards
        'active_trends': active_trends,
        'active_systems': active_systems,
        'active_levels': active_levels,
        'active_subjects': active_subjects,
        'recent_users': recent_users,
        'recent_trends': recent_trends,
    })
    
def load_education_levels(request):
    system_id = request.GET.get('system_id')
    levels = EducationLevel.objects.filter(system_id=system_id).order_by('order')
    return render(request, 'level_dropdown.html', {'levels': levels})

def load_programs(request):
    institution_id = request.GET.get('institution_id')
    programs = Program.objects.filter(institution_id=institution_id)
    return render(request, 'program_dropdown.html', {'programs': programs})

def load_years(request):
    program_id = request.GET.get('program_id')
    years = Year.objects.filter(program_id=program_id).order_by('order')
    return render(request, 'year_dropdown.html', {'years': years})


@login_required
def create_trend(request):
    if request.method == 'POST':
        form = TrendForm(request.POST, user=request.user)
        if form.is_valid():
            trend = form.save()
            
            # Automatically become a setter when creating first trend
            profile = request.user.profile
            if profile.role == UserRole.PARTICIPANT:  # Use constant
                profile.role = UserRole.SETTER  # Use constant
                profile.save()
                
            messages.success(request, 'Trend created successfully!')
            return redirect('dashboard')
    else:
        form = TrendForm(user=request.user)
    return render(request, 'trend/create_trend.html', {'form': form})

# trends/views.py - Update login_view
def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            if user:
                login(request, user)
                
                # Check if we're on a subdomain
                institution = getattr(request, 'institution', None)
                if institution:
                    # Redirect to institution dashboard
                    return redirect('institution_dashboard')
                else:
                    # Redirect to main dashboard or institution switch
                    return redirect('institution_switch')
            messages.error(request, 'Invalid credentials')
    else:
        form = LoginForm()
    
    # Get institution context for template
    institution = getattr(request, 'institution', None)
    
    return render(request, 'trend/login.html', {
        'form': form,
        'institution': institution
    })

@login_required
def logout_view(request):
    logout(request)
    return redirect('login')


def register_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Registration successful!')
            return redirect('welcome')  # Redirect to welcome page
    
    else:
        form = RegisterForm()
    return render(request, 'trend/register.html', {'form': form})

# Add a new welcome view
def welcome_view(request):
    return render(request, 'trend/welcome.html')

# Update edit_profile view
@login_required
def edit_profile(request):
    try:
        profile = request.user.profile
    except Profile.DoesNotExist:
        # This should never happen with signals, but just in case
        profile = Profile.objects.create(user=request.user)
    
    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('dashboard')
    else:
        form = ProfileForm(instance=profile)
    
    return render(request, 'trend/edit_profile.html', {'form': form})

# Update dashboard_view
@login_required
def dashboard_view(request):
    profile = request.user.profile  # Safe because signals ensure it exists
    trends = Trend.objects.filter(is_approved=True)
    return render(request, 'trend/dashboard.html', {
        'trends': trends,
        'profile': profile
    })

@login_required
def create_educational_system(request):
    if request.method == 'POST':
        form = EducationalSystemForm(request.POST, user=request.user)
        if form.is_valid():
            system = form.save()
            messages.success(request, f'Educational system "{system.name}" submitted for approval!')
            return redirect('dashboard')
    else:
        form = EducationalSystemForm(user=request.user)
    return render(request, 'trend/system_form.html', {'form': form})

@login_required
def create_education_level(request):  # Updated function and form name
    if request.method == 'POST':
        form = EducationLevelForm(request.POST, user=request.user)  # Updated form
        if form.is_valid():
            level = form.save()
            system_name = level.system.name if level.system else "Custom"
            messages.success(request, f'Education level "{level.name}" for {system_name} submitted for approval!')
            return redirect('dashboard')
    else:
        form = EducationLevelForm(user=request.user)  # Updated form
    return render(request, 'trend/education_level_form.html', {'form': form})  # Updated template

@login_required
def create_skill_domain(request):
    if request.method == 'POST':
        form = SkillDomainForm(request.POST, user=request.user)
        if form.is_valid():
            domain = form.save()
            messages.success(request, f'Skill domain "{domain.name}" submitted for approval!')
            return redirect('dashboard')
    else:
        form = SkillDomainForm(user=request.user)
    return render(request, 'trend/skill_domain_form.html', {'form': form})

@login_required
def create_institution(request):
    if request.method == 'POST':
        form = InstitutionForm(request.POST, user=request.user)
        if form.is_valid():
            institution = form.save()
            messages.success(request, f'Institution "{institution.name}" submitted for approval!')
            return redirect('dashboard')
    else:
        form = InstitutionForm(user=request.user)
    return render(request, 'trend/institution_form.html', {'form': form})

@login_required
def create_subject(request):
    if request.method == 'POST':
        form = SubjectForm(request.POST, user=request.user)
        if form.is_valid():
            subject = form.save()
            # Get context for success message
            level_name = subject.education_level.name if subject.education_level else ""
            institution_name = subject.institution.name if subject.institution else ""
            context = level_name or institution_name or "Global"
            
            messages.success(request, f'Subject "{subject.name}" for {context} submitted for approval!')
            return redirect('dashboard')
    else:
        form = SubjectForm(user=request.user)
    return render(request, 'trend/subject_form.html', {'form': form})

@login_required
def create_topic(request):
    if request.method == 'POST':
        form = TopicForm(request.POST, user=request.user)
        if form.is_valid():
            topic = form.save()
            messages.success(request, f'Topic "{topic.name}" for {topic.subject.name} submitted for approval!')
            return redirect('dashboard')
    else:
        form = TopicForm(user=request.user)
    return render(request, 'trend/topic_form.html', {'form': form})
    


@staff_member_required
def admin_dashboard(request):
    # User metrics
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    
    user_stats = {
        'total_users': User.objects.count(),
        'new_today': User.objects.filter(date_joined__date=today).count(),
        'new_this_week': User.objects.filter(date_joined__date__gte=week_ago).count(),
        'verified_users': User.objects.filter(is_verified=True).count(),
    }
    
    # Content metrics
    content_stats = {
        'pending_systems': EducationalSystem.objects.filter(is_approved=False).count(),
        'pending_levels': EducationLevel.objects.filter(is_approved=False).count(),
        'pending_subjects': Subject.objects.filter(is_approved=False).count(),
        'pending_trends': Trend.objects.filter(is_approved=False).count(),
    }
    
    # Recent activity
    recent_users = User.objects.order_by('-date_joined')[:5]
    recent_content = Trend.objects.order_by('-created_at')[:5]
    
    return render(request, 'trend/admin_dashboard.html', {
        'user_stats': user_stats,
        'content_stats': content_stats,
        'recent_users': recent_users,
        'recent_content': recent_content
    })

@staff_member_required
def admin_user_list(request):
    users = User.objects.select_related('profile').order_by('-date_joined')
    query = request.GET.get('q')
    
    if query:
        users = users.filter(
            Q(username__icontains=query) |
            Q(email__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        )
    
    return render(request, 'trend/admin_user_list.html', {'users': users})

@staff_member_required
def admin_user_detail(request, pk):
    user = get_object_or_404(User, pk=pk)
    profile = get_object_or_404(Profile, user=user)
    trends = Trend.objects.filter(creator=user)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'verify':
            user.is_verified = True
            user.save()
            messages.success(request, f"{user.username} has been verified")
        elif action == 'toggle_staff':
            user.is_staff = not user.is_staff
            user.save()
            status = "added to staff" if user.is_staff else "removed from staff"
            messages.success(request, f"{user.username} has been {status}")
        elif action == 'delete':
            user.delete()
            messages.success(request, f"{user.username} has been deleted")
            return redirect('admin_user_list')
    
    return render(request, 'trend/admin_user_detail.html', {
        'user': user,
        'profile': profile,
        'trends': trends
    })

@staff_member_required
def content_review_dashboard(request):
    # Get pending content for review
    pending = {
        'systems': EducationalSystem.objects.filter(is_approved=False),
        'levels': EducationLevel.objects.filter(is_approved=False),
        'subjects': Subject.objects.filter(is_approved=False),
        'topics': Topic.objects.filter(is_approved=False),
        'domains': SkillDomain.objects.filter(is_approved=False),
        'institutions': Institution.objects.filter(is_approved=False),
        'trends': Trend.objects.filter(is_approved=False),
    }
    
    return render(request, 'trend/content_review.html', {'pending': pending})

@staff_member_required
def approve_item(request, model, pk):
    model_map = {
        'system': EducationalSystem,
        'level': EducationLevel,
        'subject': Subject,
        'topic': Topic,
        'domain': SkillDomain,
        'institution': Institution,
        'trend': Trend,
    }
    
    model_class = model_map.get(model)
    if not model_class:
        messages.error(request, "Invalid model type")
        return redirect('content_review')
    
    item = get_object_or_404(model_class, pk=pk)
    item.is_approved = True
    item.save()
    
    messages.success(request, f"{model.title()} approved successfully")
    return redirect('content_review')

@staff_member_required
def reject_item(request, model, pk):
    model_map = {
        'system': EducationalSystem,
        'level': EducationLevel,
        'subject': Subject,
        'topic': Topic,
        'domain': SkillDomain,
        'institution': Institution,
        'trend': Trend,
    }
    
    model_class = model_map.get(model)
    if not model_class:
        messages.error(request, "Invalid model type")
        return redirect('content_review')
    
    item = get_object_or_404(model_class, pk=pk)
    item.delete()
    
    messages.success(request, f"{model.title()} rejected and deleted")
    return redirect('content_review')

@staff_member_required
def system_metrics(request):
    # User growth
    user_growth = (
        User.objects
        .annotate(date=TruncDay('date_joined'))
        .values('date')
        .annotate(count=Count('id'))
        .order_by('date')
    )
    
    # Content distribution
    system_distribution = (
        EducationalSystem.objects
        .values('name')
        .annotate(count=Count('id'))
    )
    
    # Trend types
    trend_types = (
        Trend.objects
        .values('space_type')
        .annotate(count=Count('id'))
    )
    
    return render(request, 'trend/system_metrics.html', {
        'user_growth': list(user_growth),
        'system_distribution': list(system_distribution),
        'trend_types': list(trend_types),
    })    
    

# trends/views.py - Update register_institution view
from django.contrib.auth import login, authenticate

def register_institution(request):
    if request.method == 'POST':
        form = InstitutionRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            institution = form.save()
            
            # Log in the admin user automatically
            admin_user = institution.admin
            admin_user.backend = 'django.contrib.auth.backends.ModelBackend'  # Set authentication backend
            login(request, admin_user)
            
            messages.success(
                request, 
                f'Your institution "{institution.name}" has been registered! '
                f'You can access it at: http://{institution.subdomain}.127.0.0.1:8000'
            )
            return redirect('institution_switch')  # Redirect to institution switch page instead of dashboard
    else:
        form = InstitutionRegistrationForm()
    
    return render(request, 'trend/institution_registration.html', {'form': form})


@login_required
def create_institution_level(request):
    profile = request.user.profile
    if not profile.institution:
        return redirect('institution_dashboard')
    
    if request.method == 'POST':
        form = EducationLevelForm(request.POST, user=request.user, institution=profile.institution)
        if form.is_valid():
            level = form.save()
            messages.success(request, f'Education level "{level.name}" created!')
            return redirect('institution_dashboard')
    else:
        form = EducationLevelForm(user=request.user, institution=profile.institution)
    
    return render(request, 'trend/institution_level_form.html', {'form': form})

@login_required
def create_institution_subject(request):
    profile = request.user.profile
    if not profile.institution:
        return redirect('institution_dashboard')
    
    if request.method == 'POST':
        form = SubjectForm(request.POST, user=request.user, institution=profile.institution)
        if form.is_valid():
            subject = form.save()
            messages.success(request, f'Subject "{subject.name}" created!')
            return redirect('institution_dashboard')
    else:
        form = SubjectForm(user=request.user, institution=profile.institution)
    
    return render(request, 'trend/institution_subject_form.html', {'form': form})

@login_required
def create_institution_topic(request):
    profile = request.user.profile
    if not profile.institution:
        return redirect('institution_dashboard')
    
    if request.method == 'POST':
        form = TopicForm(request.POST, user=request.user, institution=profile.institution)
        if form.is_valid():
            topic = form.save()
            messages.success(request, f'Topic "{topic.name}" created!')
            return redirect('institution_dashboard')
    else:
        form = TopicForm(user=request.user, institution=profile.institution)
    
    return render(request, 'trend/institution_topic_form.html', {'form': form})

@login_required
def create_institution_trend(request):
    profile = request.user.profile
    if not profile.institution:
        return redirect('institution_dashboard')
    
    if request.method == 'POST':
        form = TrendForm(request.POST, user=request.user, institution=profile.institution)
        if form.is_valid():
            trend = form.save()
            trend.access_level = AccessLevel.INSTITUTIONAL
            trend.institution = profile.institution
            trend.save()
            
            messages.success(request, 'Institutional trend created successfully!')
            return redirect('institution_dashboard')
    else:
        form = TrendForm(user=request.user, institution=profile.institution)
    
    return render(request, 'trend/create_institution_trend.html', {'form': form})

# trends/views.py - Add this test view
def test_institution_registration(request):
    """Test view to verify institution creation"""
    from .models import Institution, Profile
    
    # Create a test institution manually
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    # Check if test institution already exists
    if not Institution.objects.filter(subdomain='testschool').exists():
        # Create admin user
        admin_user = User.objects.create_user(
            username='testadmin',
            email='admin@testschool.com',
            password='test123',
            first_name='Test',
            last_name='Admin',
            is_verified=True
        )
        
        # Create institution
        institution = Institution.objects.create(
            name='Test School',
            institution_type='educational',
            subdomain='testschool',
            admin=admin_user,
            is_approved=True,  # Auto-approve for testing
            is_active=True
        )
        
        # Create profile
        Profile.objects.create(
            user=admin_user,
            global_role='participant',
            institution_role='institution_admin',
            institution=institution
        )
        
        return HttpResponse(f"Test institution created: {institution.name} - Access at: testschool.127.0.0.1:8000")
    
    return HttpResponse("Test institution already exists")

# trends/views.py - Fix the subdomain_test view
import socket

def subdomain_test(request):
    """Test view to verify subdomain detection"""
    institution = getattr(request, 'institution', None)
    
    # Get local IP for display
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
    except:
        local_ip = '127.0.0.1'
    
    if institution:
        return HttpResponse(f"""
        <h1>Subdomain Test Successful! 🎉</h1>
        <p>Institution: {institution.name}</p>
        <p>Subdomain: {institution.subdomain}</p>
        <p>Type: {institution.get_institution_type_display()}</p>
        <p>You are accessing via: {request.get_host()}</p>
        <a href="/">Back to main site</a>
        """)
    else:
        return HttpResponse(f"""
        <h1>No Institution Detected</h1>
        <p>You are accessing the main site at: {request.get_host()}</p>
        <p>Try accessing via: testschool.127.0.0.1:8000</p>
        <p>Or: testschool.{local_ip}:8000</p>
        <a href="/">Back to main site</a>
        """)


@login_required
def space_detail(request, pk):
    """View space details"""
    institution = getattr(request, 'institution', None)
    if not institution:
        messages.error(request, "You must access this page through your institution's subdomain")
        return redirect('dashboard')
    
    space = get_object_or_404(Space, pk=pk, institution=institution)
    trends = Trend.objects.filter(space=space, start_time__gte=timezone.now()).order_by('start_time')
    
    context = {
        'space': space,
        'trends': trends,
        'institution': institution,
    }
    return render(request, 'trend/space_detail.html', context)

@login_required
def space_edit(request, pk):
    """Edit a space"""
    institution = getattr(request, 'institution', None)
    if not institution:
        messages.error(request, "You must access this page through your institution's subdomain")
        return redirect('dashboard')
    
    space = get_object_or_404(Space, pk=pk, institution=institution)
    
    if request.method == 'POST':
        form = SpaceForm(request.POST, instance=space, institution=institution, user=request.user)
        if form.is_valid():
            space = form.save()
            messages.success(request, f'Space "{space.name}" updated successfully!')
            return redirect('space_list')
    else:
        form = SpaceForm(instance=space, institution=institution, user=request.user)
    
    context = {
        'form': form,
        'space': space,
        'institution': institution,
        'title': 'Edit Space'
    }
    return render(request, 'trend/space_form.html', context)


@login_required
def trend_create(request):
    """Create a new trend/schedule"""
    institution = getattr(request, 'institution', None)
    if not institution:
        messages.error(request, "You must access this page through your institution's subdomain")
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = TrendForm(request.POST, institution=institution, user=request.user)
        if form.is_valid():
            trend = form.save()
            messages.success(request, f'Schedule "{trend.title}" created successfully!')
            return redirect('trend_list')
    else:
        form = TrendForm(institution=institution, user=request.user)
    
    context = {
        'form': form,
        'institution': institution,
        'title': 'Create Schedule'
    }
    return render(request, 'trend/trend_form.html', context)

@login_required
def trend_calendar(request):
    """Calendar view for trends"""
    institution = getattr(request, 'institution', None)
    if not institution:
        messages.error(request, "You must access this page through your institution's subdomain")
        return redirect('dashboard')
    
    # Get trends for the current month
    today = timezone.now()
    first_day = today.replace(day=1)
    last_day = (first_day + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    
    trends = Trend.objects.filter(
        institution=institution,
        start_time__range=[first_day, last_day]
    )
    
    context = {
        'trends': trends,
        'institution': institution,
        'current_month': today.strftime('%B %Y'),
    }
    return render(request, 'trend/trend_calendar.html', context)


@login_required
def user_invite(request):
    """Invite new users to the institution"""
    institution = getattr(request, 'institution', None)
    if not institution:
        messages.error(request, "You must access this page through your institution's subdomain")
        return redirect('dashboard')
    
    if request.method == 'POST':
        email = request.POST.get('email')
        role = request.POST.get('role')
        
        # Check if user already exists
        try:
            user = User.objects.get(email=email)
            # User exists, add to institution
            profile, created = Profile.objects.get_or_create(user=user)
            profile.institution = institution
            profile.institution_role = role
            profile.save()
            
            messages.success(request, f"User {email} added to institution as {role}")
        
        except User.DoesNotExist:
            # Create new user account
            username = email.split('@')[0]
            password = User.objects.make_random_password()
            
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                is_verified=True
            )
            
            profile = Profile.objects.create(
                user=user,
                institution=institution,
                institution_role=role,
                global_role='participant'
            )
            
            # TODO: Send invitation email with credentials
            messages.success(request, f"Invitation sent to {email}")
        
        return redirect('user_management')
    
    context = {
        'institution': institution,
        'roles': UserRole.CHOICES,
    }
    return render(request, 'trend/user_invite.html', context)

@login_required
def user_edit_role(request, user_id):
    """Edit user role within institution"""
    institution = getattr(request, 'institution', None)
    if not institution:
        messages.error(request, "You must access this page through your institution's subdomain")
        return redirect('dashboard')
    
    try:
        profile = Profile.objects.get(user_id=user_id, institution=institution)
        
        if request.method == 'POST':
            new_role = request.POST.get('role')
            profile.institution_role = new_role
            profile.save()
            
            messages.success(request, f"Updated {profile.user.username}'s role to {new_role}")
            return redirect('user_management')
        
        context = {
            'institution': institution,
            'profile': profile,
            'roles': UserRole.CHOICES,
        }
        return render(request, 'trend/user_edit_role.html', context)
    
    except Profile.DoesNotExist:
        messages.error(request, "User not found in this institution")
        return redirect('user_management')

    
# trends/views.py - Update views to handle both individual and institutional access
@login_required
def space_list(request):
    """List spaces - can be individual or institutional"""
    institution = getattr(request, 'institution', None)
    
    if institution:
        # Institutional access - show only institution spaces
        spaces = Space.objects.filter(institution=institution)
        template_context = {'institution': institution}
    else:
        # Individual access - show user's personal spaces
        spaces = Space.objects.filter(created_by=request.user, institution__isnull=True)
        template_context = {}
    
    # Filter by space type if provided
    space_type = request.GET.get('space_type')
    if space_type:
        spaces = spaces.filter(space_type=space_type)
    
    context = {
        'spaces': spaces,
        'space_types': SpaceType.CHOICES,
        **template_context
    }
    return render(request, 'trends/space_list.html', context)

@login_required
def space_create(request):
    """Create space - can be individual or institutional"""
    institution = getattr(request, 'institution', None)
    
    if request.method == 'POST':
        form = SpaceForm(request.POST, institution=institution, user=request.user)
        if form.is_valid():
            space = form.save()
            if institution:
                messages.success(request, f'Institutional space "{space.name}" created successfully!')
            else:
                messages.success(request, f'Personal space "{space.name}" created successfully!')
            return redirect('space_list')
    else:
        form = SpaceForm(institution=institution, user=request.user)
    
    title = 'Create Space'
    if institution:
        title = f'Create Space - {institution.name}'
    
    context = {
        'form': form,
        'title': title,
        'institution': institution,
    }
    return render(request, 'trend/space_form.html', context)

@login_required 
def trend_list(request):
    """List trends - can be individual or institutional"""
    institution = getattr(request, 'institution', None)
    
    if institution:
        # Institutional access
        trends = Trend.objects.filter(institution=institution)
        template_context = {'institution': institution}
    else:
        # Individual access
        trends = Trend.objects.filter(organizer=request.user, institution__isnull=True)
        template_context = {}
    
    # Filter by date range
    date_filter = request.GET.get('date_filter', 'upcoming')
    if date_filter == 'past':
        trends = trends.filter(end_time__lt=timezone.now())
    else:  # upcoming
        trends = trends.filter(end_time__gte=timezone.now())
    
    # Filter by trend type
    trend_type = request.GET.get('trend_type')
    if trend_type:
        trends = trends.filter(trend_type=trend_type)
    
    context = {
        'trends': trends,
        'trend_types': TrendType.CHOICES,
        'date_filter': date_filter,
        **template_context
    }
    return render(request, 'trends/trend_list.html', context)

@login_required
def institution_dashboard(request):
    """Dashboard that works for both individual and institutional access"""
    institution = getattr(request, 'institution', None)
    
    if institution:
        # Institutional dashboard
        spaces_count = Space.objects.filter(institution=institution).count()
        trends_count = Trend.objects.filter(institution=institution).count()
        users_count = Profile.objects.filter(institution=institution).count()
        
        recent_trends = Trend.objects.filter(institution=institution).order_by('-created_at')[:5]
        recent_spaces = Space.objects.filter(institution=institution).order_by('-created_at')[:5]
        
        context = {
            'institution': institution,
            'spaces_count': spaces_count,
            'trends_count': trends_count,
            'users_count': users_count,
            'recent_trends': recent_trends,
            'recent_spaces': recent_spaces,
            'dashboard_type': 'institutional'
        }
    else:
        # Personal dashboard
        spaces_count = Space.objects.filter(created_by=request.user, institution__isnull=True).count()
        trends_count = Trend.objects.filter(organizer=request.user, institution__isnull=True).count()
        
        recent_trends = Trend.objects.filter(organizer=request.user, institution__isnull=True).order_by('-created_at')[:5]
        recent_spaces = Space.objects.filter(created_by=request.user, institution__isnull=True).order_by('-created_at')[:5]
        
        context = {
            'spaces_count': spaces_count,
            'trends_count': trends_count,
            'recent_trends': recent_trends,
            'recent_spaces': recent_spaces,
            'dashboard_type': 'personal'
        }
    
    return render(request, 'trend/institution_dashboard.html', context)    

# trends/views.py - Add institution selection
def select_institution(request, institution_id):
    """Manually select an institution for testing"""
    try:
        institution = Institution.objects.get(id=institution_id, is_active=True, is_approved=True)
        request.session['current_institution_id'] = str(institution.id)
        messages.success(request, f"Now accessing: {institution.name}")
        return redirect('institution_dashboard')
    except Institution.DoesNotExist:
        messages.error(request, "Institution not found or not approved")
        return redirect('dashboard')

def institution_switch(request):
    """Page to switch between institutions"""
    if request.user.is_authenticated:
        # Get institutions user has access to
        institutions = Institution.objects.filter(
            Q(admin=request.user) | 
            Q(members__user=request.user)
        ).distinct()
    else:
        institutions = Institution.objects.filter(is_active=True, is_approved=True)
    
    return render(request, 'trend/institution_switch.html', {
        'institutions': institutions
    })    
    
# trends/views.py - Update permission checks
@login_required
def user_management(request):
    """Manage users within the institution"""
    institution = getattr(request, 'institution', None)
    if not institution:
        messages.error(request, "You must access this page through your institution's subdomain")
        return redirect('dashboard')
    
    # Check if user has permission to manage users
    # Institution admin OR user is the institution admin OR superuser
    profile = request.user.profile
    is_institution_admin = (
        profile.institution == institution and 
        profile.institution_role == UserRole.INSTITUTION_ADMIN
    )
    is_actual_admin = request.user == institution.admin
    
    if not (is_institution_admin or is_actual_admin or request.user.is_superuser):
        messages.error(request, "You don't have permission to manage users")
        return redirect('institution_dashboard')
    
    users = Profile.objects.filter(institution=institution).select_related('user')
    
    # Filter by role if provided
    role_filter = request.GET.get('role')
    if role_filter:
        users = users.filter(institution_role=role_filter)
    
    context = {
        'institution': institution,
        'users': users,
        'roles': UserRole.CHOICES,
    }
    return render(request, 'trends/user_management.html', context)

@login_required
def institution_settings(request):
    """Institution settings and configuration"""
    institution = getattr(request, 'institution', None)
    if not institution:
        messages.error(request, "You must access this page through your institution's subdomain")
        return redirect('dashboard')
    
    # Check if user has permission to edit settings
    profile = request.user.profile
    is_institution_admin = (
        profile.institution == institution and 
        profile.institution_role == UserRole.INSTITUTION_ADMIN
    )
    is_actual_admin = request.user == institution.admin
    
    if not (is_institution_admin or is_actual_admin or request.user.is_superuser):
        messages.error(request, "You don't have permission to edit institution settings")
        return redirect('institution_dashboard')
    
    if request.method == 'POST':
        form = InstitutionForm(request.POST, request.FILES, instance=institution, user=request.user)
        if form.is_valid():
            institution = form.save()
            messages.success(request, 'Institution settings updated successfully!')
            return redirect('institution_settings')
    else:
        form = InstitutionForm(instance=institution, user=request.user)
    
    context = {
        'institution': institution,
        'form': form,
    }
    return render(request, 'trends/institution_settings.html', context)   
    
