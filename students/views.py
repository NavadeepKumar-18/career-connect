from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import (
    StudentProfile,
    StudentSkill,
    Project,
    Resume
)
import logging

logger = logging.getLogger(__name__)
import mimetypes
from .services import extract_resume_text
from functools import wraps
import mimetypes
from django.views.decorators.http import require_GET,require_POST

from django.http import HttpResponseForbidden,FileResponse,Http404
def student_only(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if getattr(request.user, 'role', None) != 'STUDENT':
            return HttpResponseForbidden(
                'Only students can access this page.'
            )

        return view_func(request, *args, **kwargs)

    return wrapper
@login_required
@student_only
def student_profile(request):

    profile, created = StudentProfile.objects.get_or_create(
        user=request.user
    )

    if request.method == 'POST':

        profile.full_name = request.POST.get('full_name')
        profile.branch = request.POST.get('branch')
        profile.college = request.POST.get('college')
        profile.phone = request.POST.get('phone')
        profile.cgpa = request.POST.get('cgpa')
        profile.career_interest = request.POST.get('career_interest')

        if request.FILES.get('profile_image'):
            profile.profile_image = request.FILES.get('profile_image')

        profile.save()

        return redirect('dashboard:student_dashboard')

    return render(
        request,
        'students/profile.html',
        {
            'profile': profile
        }
    )



@login_required
@student_only
def student_skills(request):
    profile, created = StudentProfile.objects.get_or_create(
        user=request.user
    )

    if request.method == 'POST':
        skill = request.POST.get('skill', '').strip()
        proficiency = request.POST.get('proficiency', 'BEGINNER')
        skill_type = request.POST.get('skill_type', 'TECHNICAL')

        valid_proficiencies = dict(
            StudentSkill.PROFICIENCY_CHOICES
        )
        valid_skill_types = {
            'TECHNICAL',
            'SOFT',
        }

        if not skill:
            messages.error(request, 'Please enter a skill.')

        elif proficiency not in valid_proficiencies:
            messages.error(request, 'Please select a valid proficiency level.')

        elif skill_type not in valid_skill_types:
            messages.error(request, 'Please select a valid skill category.')

        else:
            StudentSkill.objects.create(
                student=profile,
                skill=skill,
                proficiency=proficiency,
                skill_type=skill_type,
            )

            messages.success(
                request,
                f'{skill} added successfully.'
            )

        return redirect('student_skills')

    skills = StudentSkill.objects.filter(
        student=profile
    ).order_by('skill_type', 'skill')

    return render(
        request,
        'students/skills.html',
        {
            'skills': skills,
            'proficiency_choices': StudentSkill.PROFICIENCY_CHOICES,
        }
    )



@login_required
@student_only
@require_POST
def delete_skill(request, skill_id):

    profile, created = StudentProfile.objects.get_or_create(
        user=request.user
    )

    skill = StudentSkill.objects.filter(
        id=skill_id,
        student=profile
    ).first()

    if skill:
        skill.delete()
        messages.success(request, 'Skill deleted successfully.')

    return redirect('student_skills')


@login_required
@student_only
def student_projects(request):

    profile, created = StudentProfile.objects.get_or_create(
        user=request.user
    )

    if request.method == 'POST':

        title = request.POST.get('title')
        description = request.POST.get('description')
        technologies = request.POST.get('technologies')

        if title and description and technologies:

            Project.objects.create(
                student=profile,
                title=title,
                description=description,
                technologies=technologies
            )

        return redirect('student_projects')

    projects = Project.objects.filter(
        student=profile
    ).order_by('-created_at')

    return render(
        request,
        'students/projects.html',
        {
            'projects': projects
        }
    )


@login_required
@student_only
@require_POST
def delete_project(request, project_id):

    profile, created = StudentProfile.objects.get_or_create(
        user=request.user
    )

    project = Project.objects.filter(
        id=project_id,
        student=profile
    ).first()

    if project:
        project.delete()
        messages.success(request, 'Project deleted successfully.')

    return redirect('student_projects')



@login_required
@student_only
def student_resume(request):
    profile, created = StudentProfile.objects.get_or_create(
        user=request.user
    )

    resume = Resume.objects.filter(student=profile).first()

    if request.method == 'POST':
        resume_file = request.FILES.get('resume_file')

        if not resume_file:
            messages.error(request, 'Please select a resume file.')
            return redirect('student_resume')

        allowed_extensions = ('.pdf', '.docx')
        file_name = resume_file.name.lower()

        if not file_name.endswith(allowed_extensions):
            messages.error(
                request,
                'Only PDF and DOCX files are allowed.'
            )
            return redirect('student_resume')

        max_size = 5 * 1024 * 1024
        if resume_file.size > max_size:
            messages.error(
                request,
                'Resume size must be less than 5 MB.'
            )
            return redirect('student_resume')

        # Store the new upload temporarily so the existing resume
        # is not overwritten before extraction succeeds.
        import os
        import tempfile

        suffix = os.path.splitext(file_name)[1]

        try:
            with tempfile.NamedTemporaryFile(
                suffix=suffix,
                delete=False
            ) as temp_file:
                for chunk in resume_file.chunks():
                    temp_file.write(chunk)
                temp_path = temp_file.name

            try:
                extracted_text = extract_resume_text(temp_path)
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)

            if not extracted_text.strip():
                messages.error(
                    request,
                    'No readable text was found. Please upload a '
                    'text-readable PDF or DOCX resume. Your existing '
                    'resume, if any, has not been changed.'
                )
                return redirect('student_resume')
            # Reset file pointer before uploading to Cloudinary.
            resume_file.seek(0)
            # Save only after text extraction succeeds.
            if resume:
                resume.resume_file = resume_file
                resume.extracted_text = extracted_text
                resume.save()
            else:
                resume = Resume.objects.create(
                    student=profile,
                    resume_file=resume_file,
                    extracted_text=extracted_text
                )

            messages.success(
                request,
                'Resume uploaded and text extracted successfully.'
            )

        except Exception:
         logger.exception("Resume upload or processing failed")

         messages.error(
        request,
        'Unable to process this resume. Please upload a valid '
        'PDF or DOCX file.'
    )

        return redirect('student_resume')

    return render(
        request,
        'students/resume.html',
        {'resume': resume}
    )


@login_required
@student_only
@require_POST
def delete_resume(request):

    profile, created = StudentProfile.objects.get_or_create(
        user=request.user
    )

    resume = Resume.objects.filter(
        student=profile
    ).first()

    if resume:
        resume.resume_file.delete(save=False)
        resume.delete()

        messages.success(
            request,
            'Resume deleted successfully.'
        )

    return redirect('student_resume')

def home(request):
    return render(request, 'home.html')


@login_required
@require_GET
def student_resume_download(request, resume_id):

    resume = Resume.objects.select_related(
        'student',
        'student__user'
    ).filter(pk=resume_id).first()

    if resume is None:
        raise Http404('Resume not found.')

    role = getattr(request.user, 'role', None)

    is_owner = (
        role == 'STUDENT'
        and resume.student.user_id == request.user.id
    )

    is_admin = role == 'ADMIN'

    if not (is_owner or is_admin):
        return HttpResponseForbidden(
            'You are not authorized to access this resume.'
        )

    try:
        file_handle = resume.resume_file.open('rb')
    except (FileNotFoundError, OSError, ValueError):
        raise Http404('Resume file is unavailable.')

    filename = resume.resume_file.name.rsplit('/', 1)[-1]

    content_type, _ = mimetypes.guess_type(filename)

    response = FileResponse(
        file_handle,
        as_attachment=(content_type != 'application/pdf'),
        filename=filename,
        content_type=content_type or 'application/octet-stream',
    )

    response['X-Content-Type-Options'] = 'nosniff'
    response['Cache-Control'] = 'private, no-store'

    return response
