from django.urls import path
from . import views

app_name = 'exams'

urlpatterns = [
    # Exam Set Management
    path('sets/', views.ExamSetListView.as_view(), name='exam_set_list'),
    path('sets/create/', views.exam_set_create, name='exam_set_create'),
    path('sets/<uuid:pk>/', views.ExamSetDetailView.as_view(), name='exam_set_detail'),
    path('sets/<uuid:pk>/update/', views.ExamSetUpdateView.as_view(), name='exam_set_update'),
    
    # Questions Management
    path('sets/<uuid:exam_set_id>/questions/add/', views.QuestionCreateView.as_view(), name='add_question'),
    path('questions/<uuid:pk>/update/', views.QuestionUpdateView.as_view(), name='update_question'),
    
    # Exam Taking
    path('attempt/<uuid:pk>/start/', views.ExamAttemptStartView.as_view(), name='exam_attempt_start'),
    path('attempt/<uuid:pk>/', views.ExamInterfaceView.as_view(), name='exam_interface'),
    path('attempt/<uuid:pk>/submit/', views.ExamSubmitView.as_view(), name='exam_submit'),
    
    # Grading
    path('grading/', views.GradingDashboardView.as_view(), name='grading_dashboard'),
    path('grading/attempt/<uuid:pk>/', views.GradingInterfaceView.as_view(), name='grading_interface'),
    path('grading/attempt/<uuid:pk>/submit/', views.GradingSubmitView.as_view(), name='grading_submit'),
    
    # Results
    path('results/<uuid:pk>/', views.ExamResultView.as_view(), name='exam_result'),
    path('results/', views.ExamResultListView.as_view(), name='exam_result_list'),
    
    # Corrections
    path('corrections/<uuid:exam_set_id>/add/', views.CorrectionCreateView.as_view(), name='correction_create'),

    path('sets/<uuid:set_id>/add/mcq/', views.add_mcq_question, name='add_mcq_question'),
    path('sets/<uuid:set_id>/add/text/', views.add_text_question, name='add_text_question'),
    path('sets/<uuid:set_id>/questions/<uuid:question_id>/edit/', views.edit_question, name='edit_question'),
]