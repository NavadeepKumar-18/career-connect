from django.urls import path
from . import views

urlpatterns = [
    path('profile/', views.student_profile, name='student_profile'),

    path('skills/', views.student_skills, name='student_skills'),
    path(
        'skills/delete/<int:skill_id>/',
        views.delete_skill,
        name='delete_skill'
    ),

    path('projects/', views.student_projects, name='student_projects'),
    path(
        'projects/delete/<int:project_id>/',
        views.delete_project,
        name='delete_project'
    ),

    path('resume/', views.student_resume, name='student_resume'),
    path(
        'resume/delete/',
        views.delete_resume,
        name='delete_resume'
    ),
    path(
    'resume/<int:resume_id>/download/',
    views.student_resume_download,
    name='student_resume_download'
),
]