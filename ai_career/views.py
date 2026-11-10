from django.contrib.auth.decorators import login_required
from django.shortcuts import render,redirect
from .models import CareerChatMessage
from .services import (
    analyze_career_match,
    create_learning_roadmap,
    get_recommended_jobs,
    get_ineligible_jobs,
    get_readiness_analysis,
    get_career_assistant_response,
    StudentProfile
)
import json
import logging
logger = logging.getLogger(__name__)
from django.contrib.auth import get_user_model

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse,StreamingHttpResponse
from django.views.decorators.http import require_POST

from students.models import StudentProfile,Resume,StudentSkill,Project
from jobs.models import Job,Application,Company
from django.db.models import Q
from .local_ai import generate_career_answer,stream_career_answer
from .services import is_branch_eligible
from django.utils import timezone

@login_required
def career_recommendation(request):
    if request.user.role != "STUDENT":
        return render(
            request,
            "ai_career/career_recommendation.html",
            {
                "error": (
                    "Only students can use Career Intelligence."
                ),
                "best_career": None,
                "other_careers": [],
                "roadmap": [],
            },
        )

    results = analyze_career_match(request.user)

    best_career = results[0] if results else None
    other_careers = results[1:] if len(results) > 1 else []

    profile = StudentProfile.objects.filter(
        user=request.user
    ).first()

    roadmap = []

    if best_career:
        roadmap = create_learning_roadmap(
            best_career,
            profile=profile,
        )

    context = {
        "best_career": best_career,
        "other_careers": other_careers,
        "roadmap": roadmap,
    }

    if not results:
        context["error"] = (
            "Career recommendations could not be generated. "
            "Please check your profile and try again."
        )

    return render(
        request,
        "ai_career/career_recommendation.html",
        context,
    )

@login_required
def recommended_jobs(request):
    if request.user.role != 'STUDENT':
        return render(
            request,
            'ai_career/recommended_jobs.html',
            {
                'error': (
                    'Only students can use AI Job Recommendations.'
                )
            }
        )

    student_profile, _ = StudentProfile.objects.get_or_create(
        user=request.user
    )

    recommendations = get_recommended_jobs(request.user)
    ineligible_jobs = get_ineligible_jobs(request.user)

    return render(
        request,
        'ai_career/recommended_jobs.html',
        {
            'recommendations': recommendations,
            'ineligible_jobs': ineligible_jobs,
            'student_cgpa': student_profile.cgpa,
        }
    )

@login_required
def career_readiness(request):

    if request.user.role != 'STUDENT':
        return render(
            request,
            'ai_career/career_readiness.html',
            {
                'error': 'Only students can access Career Readiness.'
            }
        )

    analysis = get_readiness_analysis(request.user)

    return render(
        request,
        'ai_career/career_readiness.html',
        {
            'analysis': analysis,
        }
    )


@login_required
def career_assistant(request):
    if request.user.role != 'STUDENT':
        return render(
            request,
            'ai_career/career_assistant.html',
            {
                'error': 'Only students can use the Career Assistant.',
                'answer': None,
                'question': '',
            }
        )

    answer = None
    question = ''

    if request.method == 'POST':
        question = request.POST.get("question", "").strip()

        if question:
            answer = get_career_assistant_response(
                request.user,
                question
            )
        else:
            answer = 'Please enter a question.'

    return render(
        request,
        'ai_career/career_assistant.html',
        {
            'answer': answer,
            'question': question,
        }
    )



@login_required
@require_POST
def career_copilot_api(request):
    allowed_roles = {"STUDENT", "RECRUITER", "ADMIN"}
    user_role = getattr(request.user, "role", None)

    if user_role not in allowed_roles:
        return JsonResponse(
            {"answer": "You are not authorized to use Career Copilot."},
            status=403,
        )

    question = request.POST.get("question", "").strip()

    logger.info(
        "Career Copilot request: role=%s",
        user_role,
    )

    if not question:
        return JsonResponse(
            {"answer": "Please enter a question."},
            status=400,
        )

    if len(question) > 2000:
        return JsonResponse(
            {"answer": "Please keep your question under 2,000 characters."},
            status=400,
        )
    
    if user_role == "STUDENT":
        profile, _ = StudentProfile.objects.get_or_create(
            user=request.user
        )

        jobs = Job.objects.filter(
            is_active=True,
            company__is_approved=True,
            company__recruiter__is_recruiter_approved=True,
        ).select_related("company")

        eligible_jobs = []

        for job in jobs:
            if not is_branch_eligible(
                profile.branch,
                job.eligible_branches,
            ):
                continue

            if (
                job.minimum_cgpa is not None
                and profile.cgpa is not None
                and profile.cgpa < job.minimum_cgpa
            ):
                continue

            eligible_jobs.append({
                "title": job.title,
                "company": job.company.company_name,
                "required_skills": job.required_skills,
                "minimum_cgpa": job.minimum_cgpa,
                "location": job.location,
            })

        skills = list(
            StudentSkill.objects.filter(
                student=profile
            ).values("skill", "proficiency")
        )

        projects = list(
            Project.objects.filter(
                student=profile
            ).values("title", "description", "technologies")
        )

        resume_text = ""
        try:
            resume = Resume.objects.get(student=profile)
            resume_text = (resume.extracted_text or "")[:5000]
        except Resume.DoesNotExist:
            pass

        copilot_context = {
            "role": "STUDENT",
            "instructions": (
                "Help with career planning, skills, resumes, "
                "interview preparation, and suitable jobs."
            ),
            "student": {
                "full_name": profile.full_name,
                "branch": profile.branch,
                "college": profile.college,
                "cgpa": profile.cgpa,
                "career_interest": profile.career_interest,
            },
            "registered_skills": skills,
            "projects": projects,
            "resume_text": resume_text,
            "eligible_jobs": eligible_jobs[:10],
        }


    elif user_role == "RECRUITER":
        company = Company.objects.filter(
            recruiter=request.user
        ).first()

        recruiter_data = {
            "company": company.company_name if company else None,
            "total_jobs": 0,
            "active_jobs": 0,
            "total_applications": 0,
            "applied": 0,
            "shortlisted": 0,
            "interview_scheduled": 0,
            "rejected": 0,
            "selected": 0,
            "recent_jobs": [],
            "recent_applications": [],
        }

        if company:
            jobs = Job.objects.filter(company=company)
            applications = Application.objects.filter(
                job__company=company
            )

            recruiter_data.update({
                "total_jobs": jobs.count(),
                "active_jobs": jobs.filter(
                    is_active=True
                ).count(),
                "total_applications": applications.count(),
                "applied": applications.filter(
                    status=Application.APPLIED
                ).count(),
                "shortlisted": applications.filter(
                    status=Application.SHORTLISTED
                ).count(),
                "interview_scheduled": applications.filter(
                    status=Application.INTERVIEW_SCHEDULED
                ).count(),
                "rejected": applications.filter(
                    status=Application.REJECTED
                ).count(),
                "selected": applications.filter(
                    status=Application.SELECTED
                ).count(),
                "recent_jobs": list(
                    jobs.order_by("-pk").values(
                        "id", "title", "is_active"
                    )[:10]
                ),
                "recent_applications": list(
                    applications.select_related(
                        "job"
                    ).order_by("-applied_at").values(
                        "id",
                        "job__title",
                        "status",
                        "applied_at",
                    )[:10]
                ),
            })

        copilot_context = {
            "role": "RECRUITER",
            "instructions": (
                "You are a recruiter dashboard assistant. Answer "
                "questions using the supplied company, job, and "
                "application data. Explain counts and statuses "
                "accurately. Never invent records or statistics."
            ),
            "dashboard_data": recruiter_data,
        }

    else:  # ADMIN


        User = get_user_model()

        pending_company_queryset = Company.objects.filter(
            is_approved=False,
            recruiter__role="RECRUITER",
            recruiter__is_recruiter_approved=True,
        )

        active_jobs_queryset = Job.objects.filter(
            is_active=True,
            company__is_approved=True,
            company__recruiter__role="RECRUITER",
            company__recruiter__is_recruiter_approved=True,
        ).filter(
            Q(deadline__isnull=True)
            | Q(deadline__gte=timezone.now().date())
        )

        admin_data = {
            "total_students": User.objects.filter(
                role="STUDENT"
            ).count(),
            "total_recruiters": User.objects.filter(
                role="RECRUITER"
            ).count(),
            "pending_recruiters": User.objects.filter(
                role="RECRUITER",
                is_recruiter_approved=False,
            ).count(),
            "approved_recruiters": User.objects.filter(
                role="RECRUITER",
                is_recruiter_approved=True,
            ).count(),
            "pending_recruiters_list": list(
                User.objects.filter(
                    role="RECRUITER",
                    is_recruiter_approved=False,
                ).order_by("-date_joined").values(
                    "id", "username", "email"
                )[:5]
            ),
            "total_companies": Company.objects.count(),
            "approved_companies": Company.objects.filter(
                is_approved=True,
                recruiter__role="RECRUITER",
                recruiter__is_recruiter_approved=True,
            ).count(),
            "pending_companies": pending_company_queryset.count(),
            "pending_company_list": list(
                pending_company_queryset.order_by(
                    "-created_at"
                ).values("id", "company_name")[:5]
            ),
            "total_jobs": Job.objects.count(),
            "active_jobs": active_jobs_queryset.count(),
            "total_applications": Application.objects.count(),
            "applied_applications": Application.objects.filter(
                status=Application.APPLIED
            ).count(),
            "shortlisted_applications": Application.objects.filter(
                status=Application.SHORTLISTED
            ).count(),
            "interview_applications": Application.objects.filter(
                status=Application.INTERVIEW_SCHEDULED
            ).count(),
            "rejected_applications": Application.objects.filter(
                status=Application.REJECTED
            ).count(),
            "selected_applications": Application.objects.filter(
                status=Application.SELECTED
            ).count(),
            "total_placed_students": (
                Application.objects.filter(
                    status=Application.SELECTED
                ).values("student_id").distinct().count()
            ),
            "recent_applications": list(
                Application.objects.select_related(
                    "student__user", "job__company"
                ).order_by("-applied_at").values(
                    "id",
                    "student__user__username",
                    "job__title",
                    "job__company__company_name",
                    "status",
                    "applied_at",
                )[:8]
            ),
        }

        copilot_context = {
            "role": "ADMIN",
            "instructions": (
                "You are an administrator dashboard assistant. "
                "Answer questions about students, recruiters, "
                "company approvals, jobs, applications, and "
                "placements using dashboard_data. For lists, "
                "describe only the records provided. Never invent "
                "statistics or claim access to unprovided data."
            ),
            "dashboard_data": admin_data,
        }


    context_json = json.dumps(
        copilot_context,
        ensure_ascii=False,
        default=str,
    )
    
    def stream_response():
        answer_parts = []

        try:
            history = list(
                CareerChatMessage.objects.filter(
                    user=request.user
                ).order_by("-created_at", "-pk")[:6]
            )
            history.reverse()

            CareerChatMessage.objects.create(
                user=request.user,
                role="user",
                message=question,
            )

            for event in stream_career_answer(
                question=question,
                student_context=context_json,
                conversation_history=[
                    {"role": msg.role, "content": msg.message}
                    for msg in history
                ],
            ):
                if event.get("type") == "token":
                    answer_parts.append(event.get("content", ""))

                yield json.dumps(
                    event, ensure_ascii=False
                ) + "\n"

                if event.get("type") == "error":
                    return

            answer = "".join(answer_parts).strip()

            if answer:
                CareerChatMessage.objects.create(
                    user=request.user,
                    role="assistant",
                    message=answer,
                )

        except Exception:
            logger.exception("Career Copilot streaming failed")
            yield json.dumps({
                "type": "error",
                "content": (
                    "Unable to complete the AI response. "
                    "Please try again."
                ),
            }) + "\n"

    response = StreamingHttpResponse(
        stream_response(),
        content_type="application/x-ndjson; charset=utf-8",
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response



@login_required
def career_copilot_page(request):
   allowed_roles = {"STUDENT", "RECRUITER", "ADMIN"}

   if getattr(request.user, "role", None) not in allowed_roles:
      return redirect("dashboard")

   return render(
        request,
        "ai_career/copilot.html",
    )