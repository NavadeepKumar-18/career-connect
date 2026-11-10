
from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('student/', views.student_dashboard, name='student_dashboard'),
    path('recruiter/', views.recruiter_dashboard, name='recruiter_dashboard'),
    path('admin/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/recruiter-approvals/', views.admin_recruiter_approvals, name='admin_recruiter_approvals'),
    path('home/', views.home, name='home'),
    path('admin/approve-recruiter/<int:recruiter_id>/', views.approve_recruiter_account, name='approve_recruiter_account'),
    path('admin/recruiter-approvals/<int:company_id>/approve/', views.approve_company_recruiter, name='approve_company_recruiter'),
    path(
    'jobs/<int:job_id>/',
    views.admin_job_detail,
    name='admin_job_detail'
),
path(
    'admin/students/<int:student_id>/',
    views.admin_student_detail,
    name='admin_student_detail'
),
]
