from django.urls import path
from . import views

urlpatterns = [
    path('company/profile/', views.company_profile, name='company_profile'),

    path('post/', views.post_job, name='post_job'),

    path('my-jobs/', views.recruiter_jobs, name='recruiter_jobs'),

    path(
        'my-jobs/toggle/<int:job_id>/',
        views.toggle_job_status,
        name='toggle_job_status'
    ),

    path('list/', views.job_list, name='job_list'),

    path(
        'my-applications/',
        views.my_applications,
        name='my_applications'
    ),

    # Recruiter applications
    path(
        'applications/',
        views.recruiter_applications,
        name='recruiter_applications'
    ),

    path(
        'applications/<int:application_id>/status/',
        views.update_application_status,
        name='update_application_status'
    ),
    path(
    'applications/bulk-update/',
    views.bulk_update_application_status,
    name='bulk_update_application_status',
),

    path(
        '<int:job_id>/',
        views.job_detail,
        name='job_detail'
    ),

    path(
        '<int:job_id>/apply/',
        views.apply_job,
        name='apply_job'
    ),
    path(
    'my-notifications/',
    views.student_notifications,
    name='student_notifications'
),
path(
    'notifications/<int:notification_id>/read/',
    views.mark_notification_read,
    name='mark_notification_read'
),
path(
    'notifications/mark-all-read/',
    views.mark_all_notifications_read,
    name='mark_all_notifications_read'
),
path(
    'applications/<int:application_id>/resume/',
    views.recruiter_application_resume,
    name='recruiter_application_resume'
),
]