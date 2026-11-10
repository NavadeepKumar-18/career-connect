from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.http import HttpResponseForbidden
from jobs.models import Notification,Job,Application
from django.db.models import Count
from django.contrib.auth import get_user_model
from django.http import HttpResponseForbidden
from accounts.models import User
from jobs.models import Company
from students.models import StudentProfile
from django.db.models import Q
from django.utils import timezone
def home(request):
    return render(request,'home.html')

@login_required
def student_dashboard(request):
    if getattr(request.user, 'role', None) != 'STUDENT':
        return HttpResponseForbidden(
            'Only students can access this dashboard.'
        )
    profile, created = StudentProfile.objects.get_or_create(
        user=request.user
    )

    # Retrieve saved skills and projects
    skills = profile.skills.all()
    projects = profile.projects.all()

    # Retrieve the resume associated with the profile
    resume = getattr(profile, 'resume', None)

    # Calculate profile completion
    completed_fields = 0

    if profile.full_name:
        completed_fields += 1

    if profile.branch:
        completed_fields += 1

    if profile.college:
        completed_fields += 1

    if profile.phone:
        completed_fields += 1

    if profile.cgpa is not None and profile.cgpa != '':
        completed_fields += 1

    if profile.career_interest:
        completed_fields += 1

    if profile.profile_image:
        completed_fields += 1

    # Count skills, resume, and projects as additional items
    if skills.exists():
        completed_fields += 1

    if resume:
        completed_fields += 1

    if projects.exists():
        completed_fields += 1

    # Seven profile fields + skills + resume + projects = 10 items
    profile_completion = round(
        (completed_fields / 10) * 100
    )

    # Count unread notifications
    unread_notification_count = Notification.objects.filter(
        student__user=request.user,
        is_read=False
    ).count()

    # Send ALL required values to the template
    context = {
        'profile': profile,
        'skills_count': skills.count(),
        'projects_count': projects.count(),
        'profile_completion': profile_completion,
        'resume': resume,
        'unread_notification_count': unread_notification_count,
    }

    return render(
        request,
        'dashboard/student_dashboard.html',
        context
    )




@login_required
def recruiter_dashboard(request):

    # Allow only recruiters
    if request.user.role != 'RECRUITER':
        return redirect('dashboard:student_dashboard')

    today = timezone.localdate()

    # Get recruiter's company
    company = Company.objects.filter(
        recruiter=request.user
    ).first()

    # Default values
    jobs_count = 0
    active_jobs_count = 0
    expired_jobs_count = 0
    inactive_jobs_count = 0

    total_applications = 0
    pending_applications = 0

    recent_jobs = []

    if company:

        # All jobs belonging to this company
        jobs = Job.objects.filter(
            company=company
        )

        # Job statistics
        jobs_count = jobs.count()

        # Active jobs must have a future or today's deadline
        active_jobs_count = jobs.filter(
            is_active=True,
            deadline__gte=today
        ).count()

        # Expired jobs
        expired_jobs_count = jobs.filter(
            deadline__lt=today
        ).count()

        # Manually inactive jobs that have not expired
        inactive_jobs_count = jobs.filter(
            is_active=False,
            deadline__gte=today
        ).count()

        # Recent five jobs
        recent_jobs = list(
            jobs.order_by('-created_at')[:5]
        )

        # Application count for each recent job
        for job in recent_jobs:
            job.application_count = Application.objects.filter(
                job=job
            ).count()

        # Applications belonging to this company
        applications = Application.objects.filter(
            job__company=company
        )

        total_applications = applications.count()

        # Pending applications
        pending_applications = applications.filter(
            status=Application.APPLIED
        ).count()

    context = {
        'company': company,

        'today': today,

        'jobs_count': jobs_count,
        'active_jobs_count': active_jobs_count,
        'expired_jobs_count': expired_jobs_count,
        'inactive_jobs_count': inactive_jobs_count,

        'total_applications': total_applications,
        'pending_applications': pending_applications,

        'recent_jobs': recent_jobs,
    }

    return render(
        request,
        'dashboard/recruiter_dashboard.html',
        context
    )



@login_required
def admin_dashboard(request):
    if request.user.role != 'ADMIN':
        return HttpResponseForbidden(
            "You are not authorized to access this page."
        )

    User = get_user_model()

    # -----------------------------
    # Student and recruiter counts
    # -----------------------------
    total_students = User.objects.filter(
        role='STUDENT'
    ).count()

    total_recruiters = User.objects.filter(
        role='RECRUITER'
    ).count()

    pending_recruiters = User.objects.filter(
        role='RECRUITER',
        is_recruiter_approved=False
    ).count()

    approved_recruiters = User.objects.filter(
        role='RECRUITER',
        is_recruiter_approved=True
    ).count()

    pending_recruiter_list = User.objects.filter(
        role='RECRUITER',
        is_recruiter_approved=False
    ).order_by('-date_joined')[:5]

    # -----------------------------
    # Company approval analytics
    # -----------------------------
    total_companies = Company.objects.count()

    approved_companies = Company.objects.filter(
        is_approved=True,
        recruiter__role='RECRUITER',
        recruiter__is_recruiter_approved=True
    ).count()

    # Only companies whose recruiters are approved
    # should appear in the pending company approval list.
    pending_company_queryset = Company.objects.filter(
        is_approved=False,
        recruiter__role='RECRUITER',
        recruiter__is_recruiter_approved=True
    )

    pending_companies = pending_company_queryset.count()

    pending_company_list = (
        pending_company_queryset
        .select_related('recruiter')
        .order_by('-created_at')[:5]
    )

    # -----------------------------
    # Job analytics
    # -----------------------------
    total_jobs = Job.objects.count()
    # Recent posted jobs
    recent_jobs = (
    Job.objects
    .select_related('company')
    .order_by('-id')[:10]
)

    active_jobs = Job.objects.filter(
        is_active=True,
        company__is_approved=True,
        company__recruiter__role='RECRUITER',
        company__recruiter__is_recruiter_approved=True
    ).filter(
        Q(deadline__isnull=True) | Q(deadline__gte=timezone.now().date())
    ).count()

    # -----------------------------
    # Application analytics
    # -----------------------------
    total_applications = Application.objects.count()

    applied_applications = Application.objects.filter(
        status=Application.APPLIED
    ).count()

    shortlisted_applications = Application.objects.filter(
        status=Application.SHORTLISTED
    ).count()

    rejected_applications = Application.objects.filter(
        status=Application.REJECTED
    ).count()

    selected_applications = Application.objects.filter(
        status=Application.SELECTED
    ).count()

    interview_applications = Application.objects.filter(
        status=Application.INTERVIEW_SCHEDULED
    ).count()

    # Count each student once, even if selected for multiple jobs.
    total_placed_students = (
        Application.objects
        .filter(status=Application.SELECTED)
        .values('student_id')
        .distinct()
        .count()
    )

    status_labels = [
        'Applied',
        'Shortlisted',
        'Interview Scheduled',
        'Rejected',
        'Selected',
    ]

    status_values = [
        applied_applications,
        shortlisted_applications,
        interview_applications,
        rejected_applications,
        selected_applications,
    ]

    # -----------------------------
    # Recent applications
    # -----------------------------
    recent_applications = (
        Application.objects
        .select_related('student__user', 'job__company')
        .order_by('-applied_at')[:8]
    )

    # -----------------------------
    # Dashboard context
    # -----------------------------
    context = {
        'total_students': total_students,
        'total_recruiters': total_recruiters,
        'pending_recruiters': pending_recruiters,
        'approved_recruiters': approved_recruiters,
        'pending_recruiter_list': pending_recruiter_list,

        'total_companies': total_companies,
        'approved_companies': approved_companies,
        'pending_companies': pending_companies,
        'pending_company_list': pending_company_list,

        'total_jobs': total_jobs,
        'recent_jobs': recent_jobs,
'today': timezone.localdate(),
        'active_jobs': active_jobs,

        'total_applications': total_applications,
        'applied_applications': applied_applications,
        'shortlisted_applications': shortlisted_applications,
        'interview_applications': interview_applications,
        'rejected_applications': rejected_applications,
        'selected_applications': selected_applications,

        'total_placed_students': total_placed_students,

        'status_labels': status_labels,
        'status_values': status_values,
        'recent_applications': recent_applications,
    }

    return render(
        request,
        'dashboard/admin_dashboard.html',
        context
    )

@login_required
def admin_student_detail(request, student_id):

    # Only admins can view complete student information
    if request.user.role != 'ADMIN':
        return HttpResponseForbidden(
            "You are not authorized to access this page."
        )

    student = get_object_or_404(
        StudentProfile.objects
        .select_related('user')
        .prefetch_related('skills', 'projects'),
        pk=student_id
    )

    # Get resume safely (a student may not have uploaded one)
    try:
        resume = student.resume
    except StudentProfile.resume.RelatedObjectDoesNotExist:
        resume = None

    # Get all applications submitted by this student
    applications = (
        Application.objects
        .filter(student=student)
        .select_related('job', 'job__company')
        .order_by('-applied_at')
    )

    context = {
        'student': student,
        'resume': resume,
        'skills': student.skills.all(),
        'projects': student.projects.all(),
        'applications': applications,
    }

    return render(
        request,
        'dashboard/admin_student_detail.html',
        context
    )

User = get_user_model()
@login_required
def admin_recruiter_approvals(request):
    if not request.user.is_authenticated or request.user.role != 'ADMIN':
        return HttpResponseForbidden(
            "You are not authorized to access this page."
        )

    # Recruiter accounts waiting for admin approval
    pending_recruiters = User.objects.filter(
        role='RECRUITER',
        is_recruiter_approved=False
    ).order_by('-date_joined')

    # Companies belonging to approved recruiter accounts
    pending_companies = Company.objects.filter(
        is_approved=False,
        recruiter__is_recruiter_approved=True
    ).select_related('recruiter').order_by('-created_at')

    approved_companies = Company.objects.filter(
        is_approved=True,
        recruiter__is_recruiter_approved=True
    ).select_related('recruiter').order_by('-created_at')

    context = {
        'pending_recruiters': pending_recruiters,
        'pending_companies': pending_companies,
        'approved_companies': approved_companies,
    }

    return render(
        request,
        'dashboard/admin_recruiter_approvals.html',
        context
    )

@login_required
@require_POST
def approve_recruiter_account(request, recruiter_id):
    if request.user.role != 'ADMIN':
        return HttpResponseForbidden(
            "You are not authorized to perform this action."
        )

    try:
        recruiter = User.objects.get(
            id=recruiter_id,
            role='RECRUITER'
        )
    except User.DoesNotExist:
        messages.error(request, "Recruiter account not found.")
        return redirect('admin_recruiter_approvals')

    if recruiter.is_recruiter_approved:
        messages.info(request, "This recruiter is already approved.")
    else:
        recruiter.is_recruiter_approved = True
        recruiter.save(update_fields=['is_recruiter_approved'])
        messages.success(
            request,
            f"Recruiter '{recruiter.username}' approved successfully."
        )

    return redirect('dashboard:admin_recruiter_approvals')


@login_required
@require_POST
def approve_company_recruiter(request, company_id):
    if request.user.role != 'ADMIN':
        return HttpResponseForbidden(
            "You are not authorized to approve recruiters."
        )

    company = get_object_or_404(Company, pk=company_id)

    if not company.is_approved:
        company.is_approved = True
        company.save(update_fields=['is_approved'])

        messages.success(
            request,
            f'{company.company_name} has been approved successfully.'
        )
    else:
        messages.info(
            request,
            'This company is already approved.'
        )

    return redirect('dashboard:admin_recruiter_approvals')

@login_required
def admin_job_detail(request, job_id):
    if request.user.role != 'ADMIN':
        return HttpResponseForbidden(
            "You are not authorized to access this page."
        )

    job = get_object_or_404(
        Job.objects.select_related(
            'company',
            'company__recruiter'
        ),
        id=job_id
    )

    return render(
        request,
        'dashboard/admin_job_detail.html',
        {'job': job}
    )