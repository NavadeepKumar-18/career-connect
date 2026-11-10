from django.db import transaction

from django.contrib import messages
from django.http import FileResponse
from django.contrib.auth.decorators import login_required

from django.conf import settings

from django.core.mail import send_mail

from django.shortcuts import render, redirect, get_object_or_404

from django.utils import timezone

from django.views.decorators.http import require_POST
from ai_career.services import is_branch_eligible,calculate_job_match
from django.db.models import Q

from .models import Company, Job, Application, Notification

from students.models import StudentProfile,StudentSkill,Resume

from django.core.mail import send_mail
from django.conf import settings

from django.urls import reverse
from django.contrib.sites.shortcuts import get_current_site
import logging

logger = logging.getLogger(__name__)
# --------------------------------------------------

# COMPANY PROFILE

# Recruiter approval is required before company creation.

# --------------------------------------------------



JOB_BRANCH_CHOICES = [
    ("CSE", "Computer Science (CSE)"),
    ("IT", "Information Technology (IT)"),
    ("ECE", "Electronics and Communication (ECE)"),
    ("EEE", "Electrical and Electronics (EEE)"),
    ("MECHANICAL", "Mechanical"),
    ("CIVIL", "Civil"),
    ("MECHATRONICS", "Mechatronics"),
    ("E&I", "Electronics and Instrumentation (E&I)"),
    ("OTHER", "Other"),
]


def normalize_branch(branch):
    """Normalize common branch names before comparing them."""
    value = " ".join((branch or "").strip().lower().split())
    aliases = {
        "computer science": "cse",
        "computer science engineering": "cse",
        "computer science and engineering": "cse",
        "information technology": "it",
        "electronics and communication": "ece",
        "electronics and communication engineering": "ece",
        "electrical and electronics": "eee",
        "electrical and electronics engineering": "eee",
        "mechanical engineering": "mechanical",
        "civil engineering": "civil",
        "electronics and instrumentation": "e&i",
        "electronics and instrumentation engineering": "e&i",
    }
    return aliases.get(value, value)


def is_branch_eligible(student_branch, eligible_branches):
    """An empty branch list means that the job accepts every branch."""
    if not eligible_branches:
        return True
    normalized_student = normalize_branch(student_branch)
    if not normalized_student:
        return False
    allowed = {normalize_branch(branch) for branch in eligible_branches}
    return normalized_student in allowed


@login_required

def company_profile(request):



    if request.user.role != 'RECRUITER':

        messages.error(

            request,

            'Only recruiters can access the company profile.'

        )

        return redirect('student_dashboard')



    if not request.user.is_recruiter_approved:

        messages.warning(

            request,

            'Your recruiter account is awaiting admin approval. '

            'You can create your company profile after approval.'

        )

        return redirect('recruiter_dashboard')



    company, created = Company.objects.get_or_create(

        recruiter=request.user

    )



    if request.method == 'POST':



        company_name = request.POST.get('company_name', '').strip()



        if not company_name:

            messages.error(request, 'Company name is required.')

            return render(

                request,

                'jobs/company_profile.html',

                {'company': company}

            )



        company.company_name = company_name

        company.description = request.POST.get('description', '')

        company.website = request.POST.get('website', '')

        company.location = request.POST.get('location', '')



        # New company profiles remain pending until admin approval.

        if created:

            company.is_approved = False



        company.save()



        if company.is_approved:

            messages.success(

                request,

                'Company profile updated successfully.'

            )

        else:

            messages.success(

                request,

                'Company profile saved successfully. '

                'Please wait for admin approval before posting jobs.'

            )



        return redirect('company_profile')



    return render(

        request,

        'jobs/company_profile.html',

        {'company': company}

    )





# --------------------------------------------------

# POST A JOB

# Requires recruiter approval AND company approval.

# --------------------------------------------------



@login_required
def post_job(request):
    if request.user.role != 'RECRUITER':
        messages.error(request, 'Only recruiters can post jobs.')
        return redirect('student_dashboard')

    if not request.user.is_recruiter_approved:
        messages.warning(
            request,
            'Your recruiter account must be approved before posting jobs.'
        )
        return redirect('recruiter_dashboard')

    company = Company.objects.filter(
        recruiter=request.user,
        is_approved=True
    ).first()

    if not company:
        messages.warning(
            request,
            'Your company must be approved before posting jobs.'
        )
        return redirect('recruiter_dashboard')

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()

        required_skills = request.POST.get(
            'required_skills', ''
        ).strip()

        required_soft_skills = request.POST.get(
            'required_soft_skills', ''
        ).strip()

        minimum_cgpa = request.POST.get(
            'minimum_cgpa', ''
        ).strip()

        location = request.POST.get('location', '').strip()
        salary = request.POST.get('salary', '').strip()
        deadline = request.POST.get('deadline', '').strip()

        selected_branches = request.POST.getlist(
            'eligible_branches'
        )

        valid_branches = {
            value for value, label in JOB_BRANCH_CHOICES
        }

        if 'ALL' in selected_branches:
            eligible_branches = []
        else:
            eligible_branches = [
                branch for branch in selected_branches
                if branch in valid_branches
            ]

            if not eligible_branches:
                messages.error(
                    request,
                    'Select at least one branch or choose All Branches.'
                )
                return redirect('post_job')

        # Validate required fields.
        if (
            not title
            or not description
            or not required_skills
            or not deadline
        ):
            messages.error(
                request,
                'Please fill all required fields.'
            )
            return redirect('post_job')

        # Validate deadline.
        try:
            deadline_date = timezone.datetime.strptime(
                deadline, '%Y-%m-%d'
            ).date()
        except ValueError:
            messages.error(
                request,
                'Please enter a valid deadline.'
            )
            return redirect('post_job')

        if deadline_date < timezone.localdate():
            messages.error(
                request,
                'The job deadline cannot be in the past.'
            )
            return redirect('post_job')

        # Validate minimum CGPA.
        try:
            minimum_cgpa_value = minimum_cgpa or None

            if minimum_cgpa_value is not None:
                cgpa_number = float(minimum_cgpa_value)

                if not 0 <= cgpa_number <= 10:
                    messages.error(
                        request,
                        'Minimum CGPA must be between 0 and 10.'
                    )
                    return redirect('post_job')

        except (TypeError, ValueError):
            messages.error(
                request,
                'Please enter a valid minimum CGPA.'
            )
            return redirect('post_job')

        # Create the job, including optional soft skills.
        job = Job.objects.create(
            company=company,
            title=title,
            description=description,
            required_skills=required_skills,
            required_soft_skills=required_soft_skills,
            eligible_branches=eligible_branches,
            minimum_cgpa=minimum_cgpa_value,
            location=location,
            salary=salary,
            deadline=deadline_date
        )

        # Normalize comma- or semicolon-separated skill lists.
        def normalize_skills(skill_text):
            return {
                skill.strip().casefold()
                for skill in skill_text.replace(';', ',').split(',')
                if skill.strip()
            }

        required_skill_set = normalize_skills(
            required_skills
        )

        required_soft_skill_set = normalize_skills(
            required_soft_skills
        )

        students = StudentProfile.objects.select_related(
            'user'
        ).all()

        # Local testing URL. Update these after deployment.
# Generate the correct absolute URL for the job.
        job_path = reverse('job_detail', args=[job.id])
        job_url = request.build_absolute_uri(job_path)

        for student in students:
            # Check branch eligibility.
            if not is_branch_eligible(
                student.branch,
                job.eligible_branches
            ):
                continue

            # Retrieve skills and their categories.
            registered_skills = StudentSkill.objects.filter(
                student=student
            ).values_list('skill', 'skill_type')

            technical_skill_set = set()
            student_soft_skill_set = set()

            for skill, skill_type in registered_skills:
                if not skill or not skill.strip():
                    continue

                normalized_skill = skill.strip().casefold()

                if (skill_type or '').upper() == 'SOFT':
                    student_soft_skill_set.add(normalized_skill)
                else:
                    # Preserve compatibility with existing skills
                    # categorized as technical by default.
                    technical_skill_set.add(normalized_skill)

            # Calculate matching skills.
            matched_technical_skills = (
                required_skill_set & technical_skill_set
            )

            matched_soft_skills = (
                required_soft_skill_set & student_soft_skill_set
            )

            # Preserve the original notification rule:
            # students must match at least one required technical skill.
            # Soft skills are optional and do not block notifications.
            if not matched_technical_skills:
                continue

            # Enforce minimum CGPA when specified.
            if job.minimum_cgpa is not None:
                if student.cgpa is None:
                    continue

                try:
                    student_cgpa = float(student.cgpa)
                    minimum_cgpa_number = float(
                        job.minimum_cgpa
                    )
                except (TypeError, ValueError):
                    continue

                if student_cgpa < minimum_cgpa_number:
                    continue

            # Prepare matching details for the notification.
            matched_technical_text = ', '.join(
                sorted(matched_technical_skills)
            )

            if matched_soft_skills:
                matched_soft_text = ', '.join(
                    sorted(matched_soft_skills)
                )
            else:
                matched_soft_text = (
                    'No matching registered soft skills yet'
                )

            # Create one in-app notification per student and job.
            notification, created = Notification.objects.get_or_create(
                student=student,
                job=job,
                application=None,
                title='New Job Matching Your Profile',
                defaults={
                    'message': (
                        f'A new job, {job.title}, has been posted by '
                        f'{company.company_name}. '
                        f'Matched technical skills: '
                        f'{matched_technical_text}. '
                        f'Matched soft skills: {matched_soft_text}.'
                    ),
                }
            )

            # Send email only when a new notification is created.
            student_email = student.user.email

            if created and student_email:
                email_subject = (
                    f'New Job Matching Your Profile: {job.title}'
                )

                email_message = (
                    f'Hello {student.full_name},\n\n'
                    f'A new job matching your profile has been posted!\n\n'
                    f'Job Title: {job.title}\n'
                    f'Company: {company.company_name}\n'
                    f'Location: {job.location}\n'
                    f'Required Technical Skills: '
                    f'{job.required_skills}\n'
                    f'Required Soft Skills: '
                    f'{job.required_soft_skills or "Not specified"}\n'
                    f'Matched Technical Skills: '
                    f'{matched_technical_text}\n'
                    f'Matched Soft Skills: '
                    f'{matched_soft_text}\n'
                    f'Deadline: {job.deadline}\n\n'
                    f'View the job and apply here:\n'
                    f'{job_url}\n\n'
                    'Best regards,\n'
                    'Smart Career & Placement System'
                )

                try:
                    send_mail(
                        subject=email_subject,
                        message=email_message,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[student_email],
                        fail_silently=False,
                    )
                except Exception:
                    logger.exception(
                        'Failed to send job alert to student ID %s',
                        student.id
                    )

        messages.success(
            request,
            'Job posted successfully. Matching students have been notified.'
        )

        return redirect('dashboard:recruiter_dashboard')

    return render(
        request,
        'jobs/post_job.html',
        {
            'branch_choices': JOB_BRANCH_CHOICES,
        }
    )



@login_required
def recruiter_jobs(request):

    if request.user.role != 'RECRUITER':
        messages.error(
            request,
            'Only recruiters can access posted jobs.'
        )
        return redirect('student_dashboard')

    if not request.user.is_recruiter_approved:
        messages.warning(
            request,
            'Your recruiter account is awaiting admin approval.'
        )
        return redirect('recruiter_dashboard')

    company = Company.objects.filter(
        recruiter=request.user
    ).first()

    if not company:
        messages.warning(
            request,
            'Please create your company profile first.'
        )
        return redirect('company_profile')

    today = timezone.localdate()

    jobs = Job.objects.filter(
        company=company
    ).order_by('-created_at')

    context = {
        'company': company,
        'jobs': jobs,
        'today': today,
    }

    return render(
        request,
        'jobs/recruiter_jobs.html',
        context
    )



# --------------------------------------------------

# ACTIVATE / DEACTIVATE A JOB

# --------------------------------------------------




# --------------------------------------------------
# ACTIVATE / DEACTIVATE A JOB
# --------------------------------------------------

@login_required
@require_POST
def toggle_job_status(request, job_id):

    if request.user.role != 'RECRUITER':
        messages.error(
            request,
            'Only recruiters can manage jobs.'
        )
        return redirect('student_dashboard')

    if not request.user.is_recruiter_approved:
        messages.warning(
            request,
            'Your recruiter account is awaiting admin approval.'
        )
        return redirect('recruiter_dashboard')

    job = Job.objects.filter(
        id=job_id,
        company__recruiter=request.user,
        company__is_approved=True
    ).first()

    if not job:
        messages.error(
            request,
            'Job not found or your company is not approved.'
        )
        return redirect('recruiter_jobs')

    job.is_active = not job.is_active
    job.save(update_fields=['is_active'])

    if job.is_active:
        messages.success(request, 'Job activated successfully.')
    else:
        messages.success(request, 'Job deactivated successfully.')

    return redirect('recruiter_jobs')






# --------------------------------------------------

# STUDENT JOB LIST

# --------------------------------------------------




@login_required
def job_list(request):

    # Allow only students to browse jobs
    if request.user.role != 'STUDENT':
        messages.error(request, "You are not authorized to access this page.")
        return redirect('dashboard:student_dashboard')

    today = timezone.localdate()

    # Get all jobs posted by approved recruiters
    # and belonging to approved companies.
    # Do not filter by is_active or deadline here.
    jobs = Job.objects.filter(
        company__is_approved=True,
        company__recruiter__is_recruiter_approved=True
    ).select_related(
        'company',
        'company__recruiter'
    ).distinct()

    # SEARCH FILTER
    search = request.GET.get('search', '').strip()

    if search:
        jobs = jobs.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search) |
            Q(required_skills__icontains=search) |
            Q(company__company_name__icontains=search)
        )

    # LOCATION FILTER
    location = request.GET.get('location', '').strip()

    if location:
        jobs = jobs.filter(
            location__icontains=location
        )

    # Order newest jobs first
    jobs = jobs.order_by('-id')

    # Calculate application status for each job
    for job in jobs:

        job.deadline_passed = (
            job.deadline is not None
            and job.deadline < today
        )

        job.application_closed = (
            not job.is_active
            or job.deadline_passed
        )

    context = {
        'jobs': jobs,
        'search': search,
        'location': location,
        'today': today,
    }

    return render(
        request,
        'jobs/job_list.html',
        context
    )







@login_required
def job_detail(request, job_id):
    if request.user.role != 'STUDENT':
        messages.error(request, 'Only students can view job details.')
        return redirect('student_dashboard')

    # Allow viewing previously approved jobs even after expiration
    # or automatic deactivation.
    job = get_object_or_404(
        Job.objects.select_related('company', 'company__recruiter'),
        id=job_id,
        company__is_approved=True,
        company__recruiter__is_recruiter_approved=True,
    )

    today = timezone.localdate()

    deadline_passed = (
        job.deadline is not None
        and job.deadline < today
    )

    job_closed = not job.is_active or deadline_passed

    profile, created = StudentProfile.objects.get_or_create(
        user=request.user
    )

    # Branch eligibility
    student_branch = profile.branch or ""

    branch_eligible = is_branch_eligible(
        student_branch,
        job.eligible_branches
    )

    # Existing application
    application = Application.objects.filter(
        student=profile,
        job=job
    ).first()

    # CGPA eligibility
    cgpa_missing = (
        job.minimum_cgpa is not None
        and profile.cgpa is None
    )

    cgpa_ineligible = (
        job.minimum_cgpa is not None
        and profile.cgpa is not None
        and profile.cgpa < job.minimum_cgpa
    )

    # AI skill matching remains available for expired jobs.
    match_result = calculate_job_match(profile, job)

    return render(
        request,
        'jobs/job_detail.html',
        {
            'job': job,
            'application': application,
            'student_cgpa': profile.cgpa,
            'cgpa_missing': cgpa_missing,
            'cgpa_ineligible': cgpa_ineligible,
            'branch_eligible': branch_eligible,
            'student_branch': student_branch,
            'match_result': match_result,
            'today': today,
            'deadline_passed': deadline_passed,
            'job_closed': job_closed,
        }
    )





@login_required
@require_POST
def apply_job(request, job_id):
    if request.user.role != 'STUDENT':
        messages.error(request, 'Only students can apply for jobs.')
        return redirect('student_dashboard')

    today = timezone.localdate()

    # Find the approved job even if it has expired or been deactivated.
    job = get_object_or_404(
        Job.objects.select_related('company', 'company__recruiter'),
        id=job_id,
        company__is_approved=True,
        company__recruiter__is_recruiter_approved=True,
    )

    # Always reject applications for closed jobs.
    if not job.is_active or (
        job.deadline is not None and job.deadline < today
    ):
        messages.error(
            request,
            'Applications for this job are closed.'
        )
        return redirect('job_detail', job_id=job.id)

    profile, _ = StudentProfile.objects.get_or_create(
        user=request.user
    )

    if Application.objects.filter(
        student=profile,
        job=job
    ).exists():
        messages.info(
            request,
            'You have already applied for this job.'
        )
        return redirect('job_detail', job_id=job.id)

    # Branch eligibility
    if not is_branch_eligible(
        profile.branch,
        job.eligible_branches
    ):
        messages.error(
            request,
            f'This job is not open to your branch '
            f'({profile.branch or "not specified"}).'
        )
        return redirect('job_detail', job_id=job.id)

    # CGPA eligibility
    if job.minimum_cgpa is not None:
        if profile.cgpa is None:
            messages.warning(
                request,
                'Please add your CGPA to your student profile.'
            )
            return redirect('job_detail', job_id=job.id)

        if profile.cgpa < job.minimum_cgpa:
            messages.error(
                request,
                f'You cannot apply for this job. Minimum CGPA: '
                f'{job.minimum_cgpa}; your CGPA: {profile.cgpa}.'
            )
            return redirect('job_detail', job_id=job.id)

    Application.objects.create(
        student=profile,
        job=job
    )

    if request.user.email:
        try:
            send_mail(
                subject=f'Application Confirmation - {job.title}',
                message=(
                    f'Hello {profile.full_name or request.user.username},\n\n'
                    f'Your application for "{job.title}" was submitted '
                    f'successfully.\n\n'
                    f'Company: {job.company.company_name}\n'
                    f'Application Date: {today}\n\n'
                    'Best regards,\n'
                    'AI-Powered Smart Career & Placement System'
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[request.user.email],
                fail_silently=True,
            )
        except Exception:
            logger.exception(
                'Application confirmation email failed for application job %s',
                job.id
            )

    messages.success(
        request,
        f'Application submitted successfully for {job.title}.'
    )

    return redirect('job_detail', job_id=job.id)



@login_required
def my_applications(request):



    if request.user.role != 'STUDENT':

        messages.error(

            request,

            'Only students can view applications.'

        )

        return redirect('student_dashboard')



    profile, created = StudentProfile.objects.get_or_create(

        user=request.user

    )



    applications = Application.objects.filter(

        student=profile

    ).select_related(

        'job',

        'job__company'

    ).order_by('-applied_at')



    return render(

        request,

        'jobs/my_applications.html',

        {'applications': applications}

    )





# --------------------------------------------------

# RECRUITER APPLICATIONS

# --------------------------------------------------





@login_required
def recruiter_applications(request):
    if request.user.role != "RECRUITER":
        messages.error(
            request,
            "Only recruiters can view applications."
        )
        return redirect("student_dashboard")

    if not request.user.is_recruiter_approved:
        messages.warning(
            request,
            "Your recruiter account is awaiting admin approval."
        )
        return redirect("recruiter_dashboard")

    company = Company.objects.filter(
        recruiter=request.user,
        is_approved=True,
    ).first()

    if not company:
        messages.warning(
            request,
            "Your company must be approved before you can view applications."
        )
        return redirect("dashboard:recruiter_dashboard")

    applications = list(
        Application.objects.filter(
            job__company=company,
        )
    .select_related(
    "student",
    "student__user",
    "student__resume",
    "job",
    "job__company",
)
        .prefetch_related(
            "student__skills",
            "student__projects",
        )
        .order_by("-applied_at")
    )

    # Calculate the match evidence for each application.
    for application in applications:
        try:
            match = calculate_job_match(
                application.student,
                application.job,
            ) or {}

            application.ai_match_percentage = match.get(
                "match_percentage"
            )
            application.ai_matched_skills = match.get(
                "matched_skills", []
            )
            application.ai_missing_skills = match.get(
                "missing_skills", []
            )
            application.ai_match_error = False

        except Exception:
            logger.exception(
                "Failed to calculate job match for application %s",
                application.pk,
            )

            # None means unavailable, not a genuine 0% match.
            application.ai_match_percentage = None
            application.ai_matched_skills = []
            application.ai_missing_skills = []
            application.ai_match_error = True

    # Sort scored applications first, highest score first.
    # Preserve newest-first ordering for ties and unscored records.
    applications.sort(
        key=lambda application: (
            application.ai_match_percentage is not None,
            application.ai_match_percentage
            if application.ai_match_percentage is not None
            else -1,
            application.applied_at,
        ),
        reverse=True,
    )

    total_applicants = len(applications)

    shortlisted_count = sum(
        application.status == Application.SHORTLISTED
        for application in applications
    )
    interview_count = sum(
        application.status == Application.INTERVIEW_SCHEDULED
        for application in applications
    )
    selected_count = sum(
        application.status == Application.SELECTED
        for application in applications
    )
    rejected_count = sum(
        application.status == Application.REJECTED
        for application in applications
    )

    return render(
        request,
        "jobs/recruiter_applications.html",
        {
            "company": company,
            "applications": applications,
            "total_applicants": total_applicants,
            "shortlisted_count": shortlisted_count,
            "interview_count": interview_count,
            "selected_count": selected_count,
            "rejected_count": rejected_count,
        },
    )


@login_required
def recruiter_application_resume(request, application_id):
    """
    Allow only the approved recruiter who owns the job
    to download the applicant's uploaded resume.
    """

    if request.user.role != 'RECRUITER':
        messages.error(
            request,
            'Only recruiters can access applicant resumes.'
        )
        return redirect('student_dashboard')

    if not request.user.is_recruiter_approved:
        messages.warning(
            request,
            'Your recruiter account is awaiting approval.'
        )
        return redirect('recruiter_dashboard')

    application = get_object_or_404(
        Application.objects.select_related(
            'student',
            'job',
            'job__company'
        ),
        id=application_id,
        job__company__recruiter=request.user,
        job__company__is_approved=True
    )

    resume = get_object_or_404(
        Resume,
        student=application.student
    )

    try:
        file_handle = resume.resume_file.open('rb')

        filename = resume.resume_file.name.rsplit('/', 1)[-1]

        return FileResponse(
            file_handle,
            as_attachment=True,
            filename=filename
        )

    except (FileNotFoundError, OSError):
        messages.error(
            request,
            'The uploaded resume file could not be accessed.'
        )
        return redirect('recruiter_applications')






# --------------------------------------------------

# UPDATE APPLICATION STATUS

# Sends in-app notification and email to the student.

# --------------------------------------------------



@login_required
@require_POST
def update_application_status(request, application_id):

    if request.user.role != 'RECRUITER':
        messages.error(
            request,
            'Only recruiters can update application status.'
        )
        return redirect('student_dashboard')

    if not request.user.is_recruiter_approved:
        messages.warning(
            request,
            'Your recruiter account is awaiting admin approval.'
        )
        return redirect('recruiter_dashboard')

    new_status = request.POST.get('status', '').strip()

    valid_statuses = dict(Application.STATUS_CHOICES)

    if new_status not in valid_statuses:
        messages.error(request, 'Invalid application status.')
        return redirect('recruiter_applications')

    # Update status and create notification together.
    with transaction.atomic():

        application = get_object_or_404(
            Application.objects.select_for_update().select_related(
                'student',
                'student__user',
                'job',
                'job__company'
            ),
            id=application_id,
            job__company__recruiter=request.user,
            job__company__is_approved=True
        )

        # Prevent duplicate notifications for unchanged status.
        if application.status == new_status:
            messages.info(
                request,
                'The application already has this status.'
            )
            return redirect('recruiter_applications')

        application.status = new_status

        application.save(update_fields=['status'])

        student = application.student
        job = application.job

        status_label = valid_statuses[new_status]

        notification_message = (
            f'Your application for {job.title} at '
            f'{job.company.company_name} has been updated to: '
            f'{status_label}.'
        )

        Notification.objects.create(
            student=student,
            application=application,
            title=f'Application {status_label}',
            message=notification_message
        )

        recipient_email = student.user.email

        student_name = (
            student.full_name or student.user.username
        )

        job_title = job.title

    # Send email after the database transaction succeeds.
    if recipient_email:

        try:
            send_mail(
                subject=f'Application Update: {job_title}',
                message=(
                    f'Hello {student_name},\n\n'
                    f'{notification_message}\n\n'
                    f'Updated on: '
                    f'{timezone.localtime().strftime("%d %B %Y, %I:%M %p")}\n\n'
                    'Please log in to your placement account '
                    'to view your application details.\n\n'
                    'Regards,\n'
                    'AI-Powered Smart Career & Placement System'
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient_email],
                fail_silently=False
            )

            messages.success(
                request,
                'Application status updated successfully. '
                'In-app notification and email sent.'
            )

        except Exception:
            logger.exception(
                'Application status email failed for application %s',
                application_id
            )

            messages.warning(
                request,
                'Application status updated and in-app notification '
                'saved, but email delivery failed.'
            )

    else:
        messages.warning(
            request,
            'Application status updated and in-app notification saved. '
            'Student email address is unavailable.'
        )

    return redirect('recruiter_applications')


@login_required
@require_POST
def bulk_update_application_status(request):
    if request.user.role != 'RECRUITER':
        messages.error(request, 'Only recruiters can update applications.')
        return redirect('student_dashboard')

    if not request.user.is_recruiter_approved:
        messages.warning(
            request,
            'Your recruiter account is awaiting admin approval.'
        )
        return redirect('recruiter_dashboard')

    company = Company.objects.filter(
        recruiter=request.user,
        is_approved=True
    ).first()

    if not company:
        messages.error(request, 'Your company must be approved first.')
        return redirect('recruiter_dashboard')

    application_ids = list(dict.fromkeys(
        request.POST.getlist('application_ids')
    ))
    new_status = request.POST.get('status', '').strip()

    valid_statuses = {
        value for value, label in Application.STATUS_CHOICES
    }

    if not application_ids:
        messages.error(request, 'Select at least one application.')
        return redirect('recruiter_applications')

    if new_status not in valid_statuses:
        messages.error(request, 'Please select a valid status.')
        return redirect('recruiter_applications')

    # Reject malformed IDs instead of silently processing a partial batch.
    try:
        application_ids = [int(value) for value in application_ids]
    except (TypeError, ValueError):
        messages.error(request, 'Invalid application selection.')
        return redirect('recruiter_applications')

    email_notifications = []

    with transaction.atomic():
        applications = list(
            Application.objects.select_for_update()
            .filter(
                id__in=application_ids,
                job__company=company,
                job__company__recruiter=request.user,
            ).select_related(
                'student',
                'student__user',
                'job',
                'job__company',
            )
        )

        # Do not update anything if even one selected application
        # does not belong to this recruiter's company.
        if len(applications) != len(set(application_ids)):
            messages.error(
                request,
                'Some selected applications were not found '
                'or do not belong to your company. Nothing was updated.'
            )
            return redirect('recruiter_applications')

        changed_count = 0

        for application in applications:
            if application.status == new_status:
                continue

            application.status = new_status
            application.save(update_fields=['status'])
            changed_count += 1

            status_label = application.get_status_display()
            student = application.student
            job = application.job

            notification_message = (
                f'Your application for {job.title} at '
                f'{job.company.company_name} has been updated to: '
                f'{status_label}.'
            )

            Notification.objects.create(
                student=student,
                application=application,
                title=f'Application {status_label}',
                message=notification_message,
            )

            recipient_email = student.user.email
            if recipient_email:
                email_notifications.append({
                    'email': recipient_email,
                    'student_name': (
                        student.full_name or student.user.username
                    ),
                    'job_title': job.title,
                    'message': notification_message,
                })

    # Send email after the database transaction succeeds.
    email_failures = 0

    for item in email_notifications:
        try:
            send_mail(
                subject=f"Application Update: {item['job_title']}",
                message=(
                    f"Hello {item['student_name']},\n\n"
                    f"{item['message']}\n\n"
                    f"Updated on: "
                    f"{timezone.localtime().strftime('%d %B %Y, %I:%M %p')}"
                    f"\n\nPlease log in to your placement account to view "
                    f"your application details.\n\n"
                    "Regards,\n"
                    "AI-Powered Smart Career & Placement System"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[item['email']],
                fail_silently=False,
            )
        except Exception:
            email_failures += 1

    if changed_count == 0:
        messages.info(
            request,
            'No changes were needed. The selected applications '
            'already have this status.'
        )
    elif email_failures:
        messages.warning(
            request,
            f'{changed_count} application(s) updated and in-app '
            f'notifications saved. {email_failures} email(s) failed.'
        )
    else:
        messages.success(
            request,
            f'{changed_count} application(s) updated successfully. '
            'In-app notifications saved and email notifications sent '
            'where email addresses were available.'
        )

    return redirect('recruiter_applications')




# --------------------------------------------------

# STUDENT NOTIFICATIONS

# --------------------------------------------------



@login_required

def student_notifications(request):



    if request.user.role != 'STUDENT':

        return redirect('student_dashboard')



    student = get_object_or_404(

        StudentProfile,

        user=request.user

    )



    notifications = Notification.objects.filter(
    student=student
).select_related(
    'job',
    'job__company',
    'application',
    'application__job'
).order_by('-created_at')


    unread_count = notifications.filter(is_read=False).count()



    return render(

        request,

        'jobs/student_notifications.html',

        {

            'notifications': notifications,

            'unread_count': unread_count,

        }

    )





# --------------------------------------------------

# MARK ONE NOTIFICATION AS READ

# --------------------------------------------------



@login_required

@require_POST

@login_required
@require_POST
def mark_notification_read(request, notification_id):



    if request.user.role != 'STUDENT':

        return redirect('student_dashboard')



    student = get_object_or_404(

        StudentProfile,

        user=request.user

    )



    notification = get_object_or_404(

        Notification,

        id=notification_id,

        student=student

    )



    notification.is_read = True

    notification.save(update_fields=['is_read'])



    return redirect('student_notifications')





# --------------------------------------------------

# MARK ALL NOTIFICATIONS AS READ

# --------------------------------------------------



@login_required

@require_POST

@login_required
@require_POST
def mark_all_notifications_read(request):



    if request.user.role != 'STUDENT':

        return redirect('student_dashboard')



    student = get_object_or_404(

        StudentProfile,

        user=request.user

    )



    Notification.objects.filter(

        student=student,

        is_read=False

    ).update(is_read=True)



    return redirect('student_notifications')
