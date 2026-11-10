
import re
import json
from groq import Groq

import logging
logger = logging.getLogger(__name__)
from django.conf import settings
from django.core.cache import cache
from .models import Career
from students.models import StudentProfile,StudentSkill
from jobs.models import Job
from django.utils import timezone
from django.db import models

import os

from django.conf import settings
from groq import Groq


def _create_client():
    """Create and return an authenticated Groq client."""
    api_key = getattr(settings, "GROQ_API_KEY", None)

    if not api_key:
        api_key = os.environ.get("GROQ_API_KEY")

    if not api_key:
        raise ValueError(
            "GROQ_API_KEY is missing. Configure it in Django settings "
            "or your environment variables."
        )

    return Groq(api_key=api_key)

def normalize_branch(branch):
    """Normalize common branch names and abbreviations."""
    value = " ".join((branch or "").strip().lower().split())

    aliases = {
        "cse": "cse",
        "computer science": "cse",
        "computer science engineering": "cse",
        "computer science and engineering": "cse",

        "it": "it",
        "information technology": "it",

        "ece": "ece",
        "electronics and communication": "ece",
        "electronics and communication engineering": "ece",

        "eee": "eee",
        "electrical and electronics": "eee",
        "electrical and electronics engineering": "eee",

        "me": "mechanical",
        "mechanical": "mechanical",
        "mechanical engineering": "mechanical",

        "ce": "civil",
        "civil": "civil",
        "civil engineering": "civil",

        "mechatronics": "mechatronics",

        "e&i": "e&i",
        "electronics and instrumentation": "e&i",
        "electronics and instrumentation engineering": "e&i",

        "other": "other",
    }

    return aliases.get(value, value)



def is_branch_eligible(student_branch, eligible_branches):
    """An empty job branch list means all branches are eligible."""

    # Jobs open to all branches should be visible to everyone.
    if not eligible_branches:
        return True

    normalized_student = normalize_branch(student_branch)

    # If the student hasn't selected a branch, don't hide the job.
    # Their eligibility must remain unverified.
    if not normalized_student:
        return True

    allowed_branches = {
        normalize_branch(branch)
        for branch in eligible_branches
        if normalize_branch(branch)
    }

    return normalized_student in allowed_branches



# --------------------------------------------------
# 1. SKILL NORMALIZATION
# --------------------------------------------------




def normalize_skill(value):
    """Normalize skill names and common aliases."""
    if not value:
        return ""

    skill = re.sub(r"\s+", " ", value.strip().casefold())

    aliases = {
        # Programming
        "js": "javascript",
        "javascript es6": "javascript",
        "ecmascript": "javascript",
        "ecmascript 6": "javascript",

        "python3": "python",
        "python 3": "python",

        # Web technologies
        "html5": "html",
        "html 5": "html",
        "css3": "css",
        "css 3": "css",

        # Frameworks
        "django framework": "django",
        "react.js": "react",
        "reactjs": "react",

        # Databases
        "postgresql db": "postgresql",
        "postgresql database": "postgresql",
        "postgres sql": "postgresql",
        "mysql database": "mysql",
    }

    return aliases.get(skill, skill)

def normalize_resume_text(text):
    """
    Normalize resume text and common skill aliases
    for accurate whole-phrase matching.
    """
    normalized = (text or "").casefold()
    normalized = re.sub(r"\s+", " ", normalized).strip()

    aliases = {
        "javascript es6": "javascript",
        "ecmascript 6": "javascript",
        "ecmascript": "javascript",
        "javascript": "javascript",
        "js": "javascript",
        "python 3": "python",
        "python3": "python",
        "html 5": "html",
        "html5": "html",
        "css 3": "css",
        "css3": "css",
        "django framework": "django",
        "react.js": "react",
        "reactjs": "react",
        "postgresql database": "postgresql",
        "postgresql db": "postgresql",
        "postgres sql": "postgresql",
    }

    for alias in sorted(aliases, key=len, reverse=True):
        pattern = (
            r"(?<![a-z0-9+#])"
            + re.escape(alias)
            + r"(?![a-z0-9+#])"
        )

        normalized = re.sub(
            pattern,
            aliases[alias],
            normalized
        )

    return normalized



# --------------------------------------------------
# 2. BASIC CAREER READINESS SCORE
# --------------------------------------------------

def calculate_readiness_score(profile, match_percentage):
    """
    Calculate a career readiness score out of 100.

    Skills: maximum 50
    Projects: maximum 20
    CGPA: maximum 15
    Resume: maximum 15
    """
    score = 0

    # Skills: maximum 50 points
    skill_count = profile.skills.count()
    score += min(skill_count * 7, 50)

    # Projects: maximum 20 points
    project_count = profile.projects.count()
    score += min(project_count * 10, 20)

    # CGPA: maximum 15 points
    if profile.cgpa is not None:
        cgpa = float(profile.cgpa)

        if cgpa >= 8:
            score += 15
        elif cgpa >= 7:
            score += 12
        elif cgpa >= 6:
            score += 9
        elif cgpa >= 5:
            score += 6

    # Resume: maximum 15 points
    if hasattr(profile, "resume"):
        score += 15

    return min(score, 100)


# --------------------------------------------------
# 3. CAREER MATCHING
# --------------------------------------------------


def analyze_career_match(user):
    """
    Generate personalized career recommendations using Groq.

    No predefined Career database records are required.
    Match percentages are calculated from the student's
    actual skills and AI-generated career requirements.
    """

    profile, _ = StudentProfile.objects.get_or_create(
        user=user
    )

    # 1. Collect student skills.
    student_skills = set()

    for item in profile.skills.all():
        if item.skill and item.skill.strip():
            normalized = normalize_skill(item.skill)

            if normalized:
                student_skills.add(normalized)

    # 2. Collect project experience.
    project_details = []

    for project in profile.projects.all():
        project_details.append({
            "title": getattr(project, "title", ""),
            "description": getattr(project, "description", ""),
            "technologies": getattr(
                project, "technologies", ""
            ),
        })

    # 3. Build the student profile for AI analysis.
    student_data = {
    "branch": str(
        getattr(profile, "branch", "") or ""
    ),
    "career_interest": str(
        getattr(profile, "career_interest", "") or ""
    ),
    "cgpa": (
        float(profile.cgpa)
        if getattr(profile, "cgpa", None) is not None
        else None
    ),
    "skills": sorted(student_skills),
    "projects": project_details,
}

    # 4. Ask Groq to generate careers dynamically.
    prompt = f"""
Analyze the following student's profile and generate
personalized career recommendations.

STUDENT PROFILE:
{json.dumps(student_data, ensure_ascii=False, default=str)}
REQUIREMENTS:

1. Generate 5 suitable career options based on the student's
   branch, existing skills, career interests, and projects.
2. Do not use a fixed or predefined career list.
3. Consider careers from software, core engineering, data,
   AI, cybersecurity, cloud, embedded systems, design,
   business, or other relevant fields as appropriate.
4. Do not force unrelated careers onto the student.
5. Generate realistic required technical and professional skills
   for each career.
6. Use concise, actionable descriptions.
7. Return valid JSON only, with this structure:

{{
  "careers": [
    {{
      "title": "Career title",
      "description": "Why this career suits the student",
      "required_skills": [
        "Skill 1",
        "Skill 2",
        "Skill 3"
      ]
    }}
  ]
}}

Return an empty careers array if there is insufficient
information to make meaningful recommendations.

Do not generate match_percentage, matched_skills,
missing_skills, or readiness_score. These will be calculated
by the application.
"""

    try:
        client = _create_client()

        response = client.chat.completions.create(
            model=getattr(
                settings,
                "GROQ_MODEL",
                "llama-3.3-70b-versatile",
            ),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert career counselor. "
                        "Generate career recommendations tailored "
                        "to the student's actual profile. "
                        "Return valid JSON only."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )

        raw_content = response.choices[0].message.content

        if not raw_content:
            return []

        ai_data = json.loads(raw_content)
        generated_careers = ai_data.get("careers", [])

    except Exception:
       logger.exception(
        "AI career recommendation generation failed for user_id=%s",user.pk,)
       return []

    # 5. Validate and score the AI-generated careers.
    results = []
    seen_titles = set()

    for career_data in generated_careers:
        if not isinstance(career_data, dict):
            continue

        title = str(
            career_data.get("title", "")
        ).strip()

        description = str(
            career_data.get("description", "")
        ).strip()

        raw_required_skills = career_data.get(
            "required_skills", []
        )

        if not title or not isinstance(
            raw_required_skills, list
        ):
            continue

        title_key = title.casefold()

        if title_key in seen_titles:
            continue

        seen_titles.add(title_key)

        required_skills = set()

        for skill in raw_required_skills:
            if not isinstance(skill, str):
                continue

            normalized = normalize_skill(skill)

            if normalized:
                required_skills.add(normalized)

        if not required_skills:
            continue

        matched_skills = (
            student_skills.intersection(required_skills)
        )

        missing_skills = (
            required_skills.difference(student_skills)
        )

        match_percentage = round(
            len(matched_skills) / len(required_skills) * 100
        )

        # Calculate readiness using your existing helper.
        readiness_score = calculate_readiness_score(
            profile,
            match_percentage,
        )

        results.append({
            # Keep a career dictionary so the template can
            # display title and description without a model.
            "career": {
                "title": title,
                "name": title,
                "description": description,
                "required_skills": sorted(required_skills),
            },
            # Also expose fields directly for the template.
            "title": title,
            "name": title,
            "description": description,
            "required_skills": sorted(required_skills),
            "match_percentage": match_percentage,
            "matched_skills": sorted(matched_skills),
            "missing_skills": sorted(missing_skills),
            "readiness_score": readiness_score,
        })

    # Highest skill-match percentage first.
    results.sort(
        key=lambda item: item["match_percentage"],
        reverse=True,
    )

    return results



# --------------------------------------------------
# 4. LEARNING ROADMAP
# --------------------------------------------------


def create_learning_roadmap(best_career, profile=None):
    """
    Create a personalized learning roadmap using:
    - Student branch
    - Career interest
    - Existing skills
    - Missing skills from career matching
    - Project technologies
    """

    branch = normalize_branch(
        getattr(profile, "branch", "") or ""
    )

    interest = (
        getattr(profile, "career_interest", "") or ""
    ).strip().casefold()

    # 1. Collect existing student skills.
    existing_skills = set()

    if profile:
        for item in profile.skills.all():
            normalized = normalize_skill(item.skill)
            if normalized:
                existing_skills.add(normalized)

        # Include technologies from student projects.
        for project in profile.projects.all():
            technologies = re.split(
                r"[,;|/\n]+",
                project.technologies or ""
            )

            for technology in technologies:
                normalized = normalize_skill(technology)
                if normalized:
                    existing_skills.add(normalized)

    # 2. Get skills missing from the best career match.
    missing_skills = (
        best_career.get("missing_skills", [])
        if best_career else []
    )

    # 3. Branch-specific foundations.
    branch_paths = {
        "cse": [
            "Programming",
            "Data Structures",
            "DBMS",
            "Git",
        ],
        "it": [
            "Programming",
            "SQL",
            "Networking",
            "Git",
        ],
        "ece": [
            "C",
            "Digital Electronics",
            "Embedded Systems",
            "Microcontrollers",
        ],
        "eee": [
            "Electrical Circuits",
            "Power Systems",
            "MATLAB",
        ],
        "mechanical": [
            "Engineering Drawing",
            "CAD",
            "Manufacturing Processes",
        ],
        "civil": [
            "Structural Analysis",
            "AutoCAD",
            "Construction Planning",
        ],
        "mechatronics": [
            "C",
            "Sensors",
            "Embedded Systems",
            "Control Systems",
        ],
    }

    # 4. Interest-specific learning paths.
    interest_paths = {
        "software development": [
            "Python",
            "Data Structures",
            "SQL",
            "Git",
        ],
        "software engineering": [
            "Python",
            "Data Structures",
            "SQL",
            "Git",
        ],
        "web development": [
            "HTML",
            "CSS",
            "JavaScript",
            "Django",
            "SQL",
        ],
        "frontend development": [
            "HTML",
            "CSS",
            "JavaScript",
            "Bootstrap",
        ],
        "backend development": [
            "Python",
            "Django",
            "SQL",
            "REST APIs",
        ],
        "data science": [
            "Python",
            "Statistics",
            "Pandas",
            "Data Visualization",
        ],
        "artificial intelligence": [
            "Python",
            "Statistics",
            "Machine Learning",
            "Data Preparation",
        ],
        "machine learning": [
            "Python",
            "Statistics",
            "Pandas",
            "Machine Learning",
        ],
        "cybersecurity": [
            "Networking",
            "Linux",
            "Python",
            "Security Fundamentals",
        ],
        "cloud computing": [
            "Linux",
            "Networking",
            "Cloud Fundamentals",
            "Git",
        ],
        "embedded systems": [
            "C",
            "Digital Electronics",
            "Microcontrollers",
            "Embedded Systems",
        ],
        "vlsi": [
            "Digital Electronics",
            "Verilog",
            "CMOS Fundamentals",
        ],
        "robotics": [
            "C",
            "Sensors",
            "Control Systems",
            "Robotics Fundamentals",
        ],
        "core engineering": [],
    }

    # Match the student's stated interest to a learning path.
    interest_skills = []

    for interest_name, skills in interest_paths.items():
        if interest_name in interest:
            interest_skills = skills
            break

    # 5. Build a prioritized list.
    # Career gaps come first, followed by interest and branch skills.
    candidates = []
    seen = set()

    sources = [
        (
            missing_skills,
            "High",
            "Career Skill Gap",
            "This skill is missing from your selected career's requirements.",
        ),
        (
            interest_skills,
            "High",
            "Career Interest",
            "This skill supports your stated career interest.",
        ),
        (
            branch_paths.get(branch, []),
            "Medium",
            "Academic Branch",
            "This skill supports your academic branch and related career options.",
        ),
    ]

    for skills, priority, phase, reason in sources:
        for skill in skills:
            normalized = normalize_skill(skill)

            if not normalized:
                continue

            # Don't recommend skills already in the profile.
            if normalized in existing_skills:
                continue

            # Avoid duplicate recommendations across sources.
            if normalized in seen:
                continue

            seen.add(normalized)

            candidates.append({
                "skill": skill.strip(),
                "priority": priority,
                "phase": phase,
                "reason": reason,
                "activity": (
                    f"Learn the fundamentals of {skill}, "
                    "practise with exercises, and apply it "
                    "in a small hands-on task."
                ),
            })

    # 6. If no recommendations remain, explain the next step.
    if not candidates:
        return []

    # 7. Add a practical project as the final step.
    candidates.append({
        "skill": "Practical Project",
        "priority": "High",
        "phase": "Practical Application",
        "reason": (
            "Use your existing knowledge and newly learned skills "
            "to demonstrate practical ability."
        ),
        "activity": (
            "Build a project relevant to your branch and career "
            "interest, document your contribution, and add it "
            "to your resume or portfolio."
        ),
    })

    return candidates


# --------------------------------------------------
# 5. JOB MATCHING
# --------------------------------------------------


def get_student_skill_evidence(student_profile):
    """Collect skills from profile entries, project technologies, and resume text."""
    skills = set()

    # 1. Skills explicitly entered by the student.
    for item in student_profile.skills.all():
        normalized = normalize_skill(item.skill)
        if normalized:
            skills.add(normalized)

    # 2. Technologies listed in student projects.
    for project in student_profile.projects.all():
        technologies = re.split(
            r"[,;|/\n]+",
            project.technologies or ""
        )
        for technology in technologies:
            normalized = normalize_skill(technology)
            if normalized:
                skills.add(normalized)

    # 3. Extracted text from the student's uploaded resume.
    resume_text = ""
    try:
        resume = student_profile.resume
        resume_text = resume.extracted_text or ""
    except (
        AttributeError,
        StudentProfile.resume.RelatedObjectDoesNotExist
    ):
        pass

    return skills, resume_text




def calculate_job_match(student_profile, job):
    """
    Calculate an explainable job-match score using technical skills,
    soft skills, projects, and resume text.

    Weights:
        - Technical skills: 70%
        - Soft skills: 30%

    If only one skill category is required, that category contributes
    100% of the score.

    Branch, CGPA, and application eligibility are evaluated separately.
    """
    student_skills, resume_text = get_student_skill_evidence(
        student_profile
    )

    def parse_skills(skill_text):
        return {
            normalize_skill(skill)
            for skill in re.split(
                r"[,;|/\n]+",
                skill_text or ""
            )
            if skill.strip()
        } - {""}

    required_skills = parse_skills(job.required_skills)
    required_soft_skills = parse_skills(
        getattr(job, "required_soft_skills", "")
    )

    # Read categorized skills registered by the student.
    registered_skills = StudentSkill.objects.filter(
        student=student_profile
    ).values_list("skill", "skill_type")

    registered_technical_skills = set()
    registered_soft_skills = set()

    for skill, skill_type in registered_skills:
        if not skill or not skill.strip():
            continue

        normalized_skill = normalize_skill(skill)

        if (skill_type or "").upper() == "SOFT":
            registered_soft_skills.add(normalized_skill)
        else:
            registered_technical_skills.add(normalized_skill)

    # get_student_skill_evidence() also supplies skills found through
    # existing evidence such as projects and resume text.
    evidence_skills = {
        normalize_skill(skill)
        for skill in student_skills
        if skill and skill.strip()
    }

    # Keep registered soft skills out of the technical skill set.
    technical_student_skills = (
        evidence_skills - registered_soft_skills
    ) | registered_technical_skills

    soft_student_skills = set(registered_soft_skills)

    # Normalize resume text for whole-phrase matching.
# Normalize resume text and common skill aliases.
    resume_text_normalized = normalize_resume_text(resume_text)

    def appears_in_resume(skill):
     pattern = (
        r"(?<![a-z0-9+#])"
        + re.escape(skill)
        + r"(?![a-z0-9+#])"
    )

     return bool(
        re.search(pattern, resume_text_normalized)
    )

    # Resume evidence for technical skills.
    for skill in required_skills:
        if appears_in_resume(skill):
            technical_student_skills.add(skill)

    # Resume evidence for soft skills.
    for skill in required_soft_skills:
        if appears_in_resume(skill):
            soft_student_skills.add(skill)

    # Calculate technical matches.
    matched_skills = (
        technical_student_skills & required_skills
    )
    missing_skills = (
        required_skills - technical_student_skills
    )

    # Calculate soft-skill matches.
    matched_soft_skills = (
        soft_student_skills & required_soft_skills
    )
    missing_soft_skills = (
        required_soft_skills - soft_student_skills
    )

    # Individual category percentages.
    technical_match_percentage = (
        round(
            len(matched_skills)
            / len(required_skills)
            * 100
        )
        if required_skills
        else None
    )

    soft_match_percentage = (
        round(
            len(matched_soft_skills)
            / len(required_soft_skills)
            * 100
        )
        if required_soft_skills
        else None
    )

    # Overall percentage. A category that has no requirements
    # does not reduce the student's score.
    if required_skills and required_soft_skills:
        match_percentage = round(
            technical_match_percentage * 0.70
            + soft_match_percentage * 0.30
        )
    elif required_skills:
        match_percentage = technical_match_percentage
    elif required_soft_skills:
        match_percentage = soft_match_percentage
    else:
        match_percentage = 0

    return {
        "job": job,
        "match_percentage": match_percentage,

        # Preserve the original keys for existing templates.
        "matched_skills": sorted(matched_skills),
        "missing_skills": sorted(missing_skills),

        # Additional soft-skill details.
        "matched_soft_skills": sorted(matched_soft_skills),
        "missing_soft_skills": sorted(missing_soft_skills),

        # Individual category scores.
        "technical_match_percentage": technical_match_percentage,
        "soft_match_percentage": soft_match_percentage,
    }


# --------------------------------------------------
# RECOMMENDED JOBS
# --------------------------------------------------

def build_job_recommendation_reasons(student_profile, job, result):
    """
    Generate transparent, profile-based explanations
    for why a job matches a student's profile.
    """
    reasons = []

    matched_technical = result["matched_skills"]
    missing_technical = result["missing_skills"]

    matched_soft = result["matched_soft_skills"]
    missing_soft = result["missing_soft_skills"]

    technical_total = len(matched_technical) + len(missing_technical)
    soft_total = len(matched_soft) + len(missing_soft)

    # Technical skill explanation
    if technical_total:
        reasons.append(
            f"You match {len(matched_technical)} of "
            f"{technical_total} required technical skills."
        )

        if missing_technical:
            reasons.append(
                "Technical skills to improve: "
                + ", ".join(missing_technical) + "."
            )

    # Soft skill explanation
    if soft_total:
        reasons.append(
            f"You match {len(matched_soft)} of "
            f"{soft_total} required soft skills."
        )

        if missing_soft:
            reasons.append(
                "Soft skills to improve: "
                + ", ".join(missing_soft) + "."
            )

    if not technical_total and not soft_total:
        reasons.append(
            "The recruiter has not specified skill requirements, "
            "so a meaningful skill match cannot be calculated."
        )

    # Branch eligibility explanation
    if job.eligible_branches:
        if student_profile.branch:
            reasons.append(
                f"Your branch ({student_profile.branch}) "
                "is accepted for this job."
            )
        else:
            reasons.append(
                "Add your branch to confirm branch eligibility."
            )
    else:
        reasons.append(
            "This job is open to students from all branches."
        )

    # CGPA explanation
    if job.minimum_cgpa is not None:
        if student_profile.cgpa is None:
            reasons.append(
                f"Your CGPA is not recorded. This job requires "
                f"a minimum CGPA of {job.minimum_cgpa}."
            )
        elif student_profile.cgpa >= job.minimum_cgpa:
            reasons.append(
                f"Your CGPA ({student_profile.cgpa}) meets "
                f"the minimum requirement ({job.minimum_cgpa})."
            )
        else:
            reasons.append(
                f"Your CGPA ({student_profile.cgpa}) is below "
                f"the required {job.minimum_cgpa}."
            )
    else:
        reasons.append(
            "This job has no specified minimum CGPA requirement."
        )

    return reasons

def get_recommended_jobs(user):
    """
    Return current jobs from approved companies,
    ranked by overall technical and soft-skill match
    and filtered by eligibility.
    """
    student_profile, _ = StudentProfile.objects.get_or_create(
        user=user
    )

    jobs = Job.objects.filter(
        is_active=True,
        company__is_approved=True,
        company__recruiter__is_recruiter_approved=True,
    ).select_related("company")

    today = timezone.localdate()

    jobs = jobs.filter(
        models.Q(deadline__isnull=True)
        | models.Q(deadline__gte=today)
    )

    recommendations = []

    for job in jobs:
        # Keep branch eligibility checks.
        if not is_branch_eligible(
            student_profile.branch,
            job.eligible_branches,
        ):
            continue

        # Exclude only when a known CGPA is too low.
        # If CGPA is missing, show the job but flag eligibility.
        if (
            job.minimum_cgpa is not None
            and student_profile.cgpa is not None
            and student_profile.cgpa < job.minimum_cgpa
        ):
            continue

        result = calculate_job_match(
            student_profile,
            job
        )
        result["recommendation_reasons"] = (
    build_job_recommendation_reasons(
        student_profile,
        job,
        result
    )
)

        notices = []

        if (
            not student_profile.branch
            and job.eligible_branches
        ):
            notices.append(
                "Add your branch to verify eligibility."
            )

        if (
            student_profile.cgpa is None
            and job.minimum_cgpa is not None
        ):
            notices.append(
                f"Add your CGPA to verify eligibility. "
                f"This job requires {job.minimum_cgpa}."
            )

        result["eligibility_notice"] = " ".join(notices)

        if not student_profile.skills.exists():
            result["profile_notice"] = (
                "Add your technical and soft skills to "
                "improve your match percentage."
            )
        else:
            result["profile_notice"] = ""

        recommendations.append(result)

    # Rank using the overall score, then total matched skills.
    recommendations.sort(
        key=lambda item: (
            item["match_percentage"],
            len(item["matched_skills"])
            + len(item["matched_soft_skills"]),
            item["job"].title.lower(),
        ),
        reverse=True,
    )

    return recommendations




def get_ineligible_jobs(user):
    """
    Return branch-eligible jobs that the student cannot apply for
    because their CGPA is below the minimum requirement.
    """
    student_profile, created = StudentProfile.objects.get_or_create(
        user=user
    )

    # Cannot determine CGPA ineligibility without a known CGPA.
    if student_profile.cgpa is None:
        return []

    jobs = Job.objects.filter(
    is_active=True,
    company__is_approved=True,
    company__recruiter__is_recruiter_approved=True,
    minimum_cgpa__isnull=False,
).filter(
    models.Q(deadline__isnull=True)
    | models.Q(deadline__gte=timezone.localdate())
).select_related("company")

    ineligible_jobs = []

    for job in jobs:
        # Exclude jobs that do not accept this student's branch.
        if not is_branch_eligible(
            student_profile.branch,
            job.eligible_branches
        ):
            continue

        if student_profile.cgpa < job.minimum_cgpa:
            result = calculate_job_match(student_profile, job)
            result["recommendation_reasons"] = (
    build_job_recommendation_reasons(
        student_profile,
        job,
        result
    )
)

            result["eligibility_reason"] = (
                f"Your CGPA ({student_profile.cgpa}) is below "
                f"the required CGPA ({job.minimum_cgpa})."
            )

            ineligible_jobs.append(result)

    return ineligible_jobs

# --------------------------------------------------
# 7. DETAILED CAREER READINESS ANALYSIS
# --------------------------------------------------

def get_readiness_analysis(user):
    """
    Generate a detailed readiness breakdown out of 100.

    Skills: maximum 40
    Projects: maximum 25
    CGPA: maximum 20
    Resume: maximum 15
    """
    profile, created = StudentProfile.objects.get_or_create(
        user=user
    )

    # Skills: maximum 40 points
    skill_count = profile.skills.count()
    skills_score = min(skill_count * 5, 40)

    # Projects: maximum 25 points
    project_count = profile.projects.count()
    projects_score = min(project_count * 12.5, 25)

    # CGPA: maximum 20 points
    cgpa_score = 0

    if profile.cgpa is not None:
        cgpa_score = round(
            min(max(float(profile.cgpa), 0), 10) * 2
        )

    # Resume: maximum 15 points
    resume_score = (
        15 if hasattr(profile, "resume") else 0
    )

    total_score = round(
        skills_score
        + projects_score
        + cgpa_score
        + resume_score
    )

    # Personalized suggestions
    recommendations = []

    if skill_count < 5:
        recommendations.append(
            "Add more relevant skills to your profile."
        )

    if project_count < 2:
        recommendations.append(
            "Build at least two practical projects and "
            "describe your contributions."
        )

    if profile.cgpa is None:
        recommendations.append(
            "Add your CGPA to complete your academic profile."
        )

    if resume_score == 0:
        recommendations.append(
            "Consider uploading a resume so recruiters "
            "can review your qualifications."
        )

    if not recommendations:
        recommendations.append(
            "Keep improving your skills and projects, "
            "and apply for relevant jobs."
        )

    return {
        "total_score": total_score,
        "skills_score": skills_score,
        "projects_score": projects_score,
        "cgpa_score": cgpa_score,
        "resume_score": resume_score,
        "skill_count": skill_count,
        "project_count": project_count,
        "recommendations": recommendations,
    }


# --------------------------------------------------
# 8. CAREER ASSISTANT
# --------------------------------------------------


def get_groq_career_response(user, question):
    """Generate personalized career guidance using Groq."""

    api_key = getattr(settings, "GROQ_API_KEY", "")
    if not question or not question.strip():
      return "Please enter a career-related question."
    

    if len(question) > 2000:
     return (
        "Your question is too long. "
        "Please keep it under 2000 characters."
    )

    if not api_key:
        return (
            "The AI assistant is currently unavailable. "
            "Please check the AI configuration."
        )

    try:
        # Retrieve the student's existing profile.
        profile = StudentProfile.objects.filter(user=user).first()

        # Build career context without sending personal contact details.
        context = {
            "branch": "",
            "career_interest": "",
            "skills": [],
            "project_technologies": [],
        }

        if profile:
            context["branch"] = profile.branch or "Not specified"
            context["career_interest"] = (
                profile.career_interest or "Not specified"
            )

            # Skills already recorded in the student profile.
            context["skills"] = sorted({
                item.skill.strip()
                for item in profile.skills.all()
                if item.skill and item.skill.strip()
            })

            # Technologies used in the student's projects.
            context["project_technologies"] = sorted({
                technology.strip()
                for project in profile.projects.all()
                for technology in (project.technologies or "").split(",")
                if technology.strip()
            })
        cache_key = f"groq_career_limit_{user.pk}"
        request_count = cache.get(cache_key, 0)

        if request_count >= 20:
         return (
        "You've reached the AI assistant usage limit. "
        "Please try again later."
    )

        if request_count == 0:
          cache.set(cache_key, 1, timeout=3600)
        else:
          cache.incr(cache_key)
        client = Groq(api_key=api_key,timeout=20.0,max_retries=1,)

        response = client.chat.completions.create(
            model=getattr(
                settings,
                "GROQ_MODEL",
                "llama-3.3-70b-versatile",
            ),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a personalized AI career assistant "
                        "for students across all academic branches, "
                        "including CSE, IT, ECE, EEE, Mechanical, "
                        "Civil, and other disciplines. "
                        "Use the supplied student context when relevant. "
                        "Recommend realistic skills, projects, learning "
                        "plans, resume improvements, interview preparation, "
                        "and career paths suited to the student's interests. "
                        "For students from non-IT branches, consider both "
                        "core-domain careers and suitable technology careers. "
                        "Explain unfamiliar technical terms simply. "
                        "Never invent job vacancies, student achievements, "
                        "or facts not supplied in the context. "
                        "For live vacancies and eligibility, advise students "
                        "to verify the actual job listing. "
                        "Give practical, clear, actionable answers."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Student career context:\n{context}\n\n"
                        f"Student question:\n{question}"
                    ),
                },
            ],
            temperature=0.4,
            max_tokens=1200,
        )

        answer = response.choices[0].message.content

        if answer and answer.strip():
            return answer.strip()

        return "I couldn't generate an answer. Please try again."

    except Exception:
      logger.exception("Groq career assistant request failed")
    return (
        "The AI assistant is temporarily unavailable. "
        "Please try again later."
    )



def get_career_assistant_response(user, question):
    """
    Provide profile-aware career guidance using existing
    rule-based analysis and Groq for general questions.
    """
    original_question = (question or "").strip()

    if not original_question:
        return (
            "Please enter a question about your career, "
            "skills, or job opportunities."
        )

    question = original_question.lower()

    # Ensure a profile exists.
    profile, created = StudentProfile.objects.get_or_create(
        user=user
    )

    # Career recommendations and readiness.
    careers = analyze_career_match(user)
    best_career = careers[0] if careers else None

    readiness = get_readiness_analysis(user)

    # 1. Best career recommendation.
    if any(word in question for word in [
        "best career",
        "suitable career",
        "which career",
        "career suits",
        "career for me",
        "career recommendation",
    ]):
        if not best_career:
            return (
                "No career recommendations are available yet. "
                "Ask your administrator to add career options."
            )

        return (
            f"Based on your current profile, your top career "
            f"match is {best_career['career'].title}, with a "
            f"{best_career['match_percentage']}% skill match. "
            f"Your matched skills are: "
            f"{', '.join(best_career['matched_skills']) or 'None yet'}. "
            f"Skills to develop: "
            f"{', '.join(best_career['missing_skills']) or 'None identified'}."
        )

    # 2. Missing skills.
    if any(word in question for word in [
        "missing skill",
        "skill gap",
        "skills am i missing",
        "skills do i need",
        "skills should i learn",
    ]):
        if not best_career:
            return (
                "No career analysis is available yet. "
                "Please try again after career options have been added."
            )

        missing = best_career["missing_skills"]

        if not missing:
            return (
                f"Your current skills cover all listed requirements "
                f"for {best_career['career'].title}. Keep practising "
                f"and building projects."
            )

        return (
            f"For {best_career['career'].title}, your missing skills "
            f"are: {', '.join(missing)}. Start with one skill at a "
            f"time and apply it in a practical project."
        )

    # 3. Personalized learning roadmap.
    if any(word in question for word in [
        "roadmap",
        "what should i learn",
        "learn next",
        "learning plan",
        "how to improve my skills",
    ]):
        if not best_career:
            return (
                "I cannot create a roadmap yet because no career "
                "options are available."
            )

        roadmap = create_learning_roadmap(best_career)

        if not roadmap:
            return (
                f"Your current skills match all listed requirements "
                f"for {best_career['career'].title}. Focus on advanced "
                f"practice, projects, and interview preparation."
            )

        steps = [
            f"{index}. {item['skill']} ({item['priority']} priority)"
            for index, item in enumerate(roadmap, start=1)
        ]

        return (
            f"Your learning roadmap for "
            f"{best_career['career'].title}:\n"
            + "\n".join(steps)
        )

    # 4. Career readiness.
    if any(word in question for word in [
        "readiness",
        "ready for placement",
        "placement ready",
        "improve my score",
        "readiness score",
    ]):
        suggestions = readiness["recommendations"]

        return (
            f"Your current career readiness score is "
            f"{readiness['total_score']}/100.\n"
            f"Skills: {readiness['skills_score']}/40; "
            f"Projects: {readiness['projects_score']}/25; "
            f"CGPA: {readiness['cgpa_score']}/20; "
            f"Resume: {readiness['resume_score']}/15.\n"
            f"Recommended actions: {' '.join(suggestions)}"
        )

    # 5. Job recommendations.
    if any(word in question for word in [
        "job",
        "jobs",
        "vacancy",
        "vacancies",
        "job match",
        "job matching",
        "apply for",
    ]):
        recommendations = get_recommended_jobs(user)

        if not recommendations:
            return (
                "There are no eligible job recommendations available "
                "right now. Complete your profile and skills, or "
                "check back when recruiters publish jobs."
            )

        answers = []

        for item in recommendations[:3]:
            job = item["job"]
            missing = item["missing_skills"]

            line = (
                f"{job.title} at {job.company.company_name}: "
                f"{item['match_percentage']}% skill match."
            )

            if missing:
                line += (
                    f" Skills to develop: {', '.join(missing)}."
                )

            answers.append(line)

        return (
            "Here are your top job matches:\n"
            + "\n".join(answers)
        )

    # 6. General questions: use Groq.
    return get_groq_career_response(user, original_question)

