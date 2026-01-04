from django.views.generic import ListView, CreateView, UpdateView, DetailView
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from .models import StudyResource, ResourceCategory, ResourceBookmark
from .forms import StudyResourceForm
from trends.models import Subject, Topic, EducationLevel, SkillDomain
from .constants import ResourceType  # IMPORTANT: Add this import
from django.conf import settings



class StudyResourceListView(ListView):
    model = StudyResource
    template_name = 'study/resource_list.html'
    context_object_name = 'resources'
    paginate_by = 12
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by resource type
        resource_type = self.request.GET.get('type')
        if resource_type and resource_type in dict(ResourceType.CHOICES):
            queryset = queryset.filter(resource_type=resource_type)
        
        # Filter by subject
        subject_id = self.request.GET.get('subject')
        if subject_id:
            queryset = queryset.filter(subjects__id=subject_id)
        
        # Filter by topic
        topic_id = self.request.GET.get('topic')
        if topic_id:
            queryset = queryset.filter(topics__id=topic_id)
        
        return queryset.select_related('creator', 'education_level').prefetch_related(
            'subjects', 'topics', 'skill_domains'
        ).order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['subjects'] = Subject.objects.all()
        context['topics'] = Topic.objects.all()
        return context

class StudyResourceCreateView(CreateView):
    model = StudyResource
    form_class = StudyResourceForm
    template_name = 'study/resource_form.html'
    success_url = reverse_lazy('study:resource_list')
    
    def form_valid(self, form):
        form.instance.creator = self.request.user
        messages.success(self.request, 'Resource created successfully!')
        return super().form_valid(form)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

class StudyResourceUpdateView(UpdateView):
    model = StudyResource
    form_class = StudyResourceForm
    template_name = 'study/resource_form.html'
    
    def get_success_url(self):
        return reverse_lazy('study:resource_detail', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        messages.success(self.request, 'Resource updated successfully!')
        return super().form_valid(form)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

class StudyResourceDetailView(DetailView):
    model = StudyResource
    context_object_name = 'resource'
    
    def get_template_names(self):
        resource_type = self.object.resource_type
        
        templates = {
            ResourceType.TEXT: 'study/resource_detail_text.html',
            ResourceType.VIDEO: 'study/resource_detail_video.html',
            ResourceType.AUDIO: 'study/resource_detail_audio.html',
            ResourceType.PDF: 'study/resource_detail_pdf.html',
        }
        return [templates.get(resource_type, 'study/resource_detail.html')]
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        resource = self.object
        
        # Generate thumbnail if missing for video
        if resource.resource_type == ResourceType.VIDEO and not resource.thumbnail:
            resource.generate_thumbnail()
            resource.save()
        
        # Check if user has bookmarked this resource
        if self.request.user.is_authenticated:
            context['is_bookmarked'] = ResourceBookmark.objects.filter(
                user=self.request.user,
                resource=resource
            ).exists()
        
        # Add related resources
        related_resources = StudyResource.objects.filter(
            subjects__in=resource.subjects.all()
        ).exclude(id=resource.id).distinct()[:5]
        
        context['related_resources'] = related_resources
        return context

def toggle_bookmark(request, pk):
    if not request.user.is_authenticated:
        return JsonResponse({'status': 'error', 'message': 'Authentication required'}, status=401)
        
    resource = get_object_or_404(StudyResource, pk=pk)
    bookmark, created = ResourceBookmark.objects.get_or_create(
        user=request.user,
        resource=resource
    )
    
    if not created:
        bookmark.delete()
    
    return JsonResponse({
        'status': 'success',
        'is_bookmarked': created
    })