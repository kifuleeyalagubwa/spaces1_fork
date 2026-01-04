from django.urls import path
from .views import (
    StudyResourceListView, StudyResourceCreateView,
    StudyResourceDetailView, StudyResourceUpdateView,
    toggle_bookmark
)

app_name = 'study'

urlpatterns = [
    path('', StudyResourceListView.as_view(), name='resource_list'),
    path('create/', StudyResourceCreateView.as_view(), name='resource_create'),
    path('<uuid:pk>/', StudyResourceDetailView.as_view(), name='resource_detail'),
    path('<uuid:pk>/edit/', StudyResourceUpdateView.as_view(), name='resource_edit'),
    path('<uuid:pk>/bookmark/', toggle_bookmark, name='toggle_bookmark'),
]