from django.conf import settings
from django.db import models
from .storage import private_resume_storage

class StudentProfile(models.Model):

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='student_profile'
    )

    full_name = models.CharField(
        max_length=100,
        blank=True
    )

    branch = models.CharField(
        max_length=100,
        blank=True
    )

    college = models.CharField(
        max_length=200,
        blank=True
    )

    phone = models.CharField(
        max_length=15,
        blank=True
    )

    cgpa = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        blank=True,
        null=True
    )

    career_interest = models.CharField(
        max_length=100,
        blank=True
    )

    profile_image = models.ImageField(
        upload_to='profile_images/',
        blank=True,
        null=True
    )

    def __str__(self):
        return self.full_name or self.user.username


class StudentSkill(models.Model):

    BEGINNER = 'BEGINNER'
    INTERMEDIATE = 'INTERMEDIATE'
    ADVANCED = 'ADVANCED'

    PROFICIENCY_CHOICES = [
        (BEGINNER, 'Beginner'),
        (INTERMEDIATE, 'Intermediate'),
        (ADVANCED, 'Advanced'),
    ]

    student = models.ForeignKey(
        StudentProfile,
        on_delete=models.CASCADE,
        related_name='skills'
    )

    skill = models.CharField(max_length=100)

    skill_type = models.CharField(
    max_length=20,
    choices=[
        ("TECHNICAL", "Technical Skill"),
        ("SOFT", "Soft Skill"),
    ],
    default="TECHNICAL",
)

    proficiency = models.CharField(
        max_length=20,
        choices=PROFICIENCY_CHOICES,
        default=BEGINNER
    )

    def __str__(self):
        return f"{self.skill} - {self.proficiency}"



class Project(models.Model):

    student = models.ForeignKey(
        StudentProfile,
        on_delete=models.CASCADE,
        related_name='projects'
    )

    title = models.CharField(max_length=200)

    description = models.TextField()

    technologies = models.CharField(max_length=300)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class Resume(models.Model):

    student = models.OneToOneField(
        StudentProfile,
        on_delete=models.CASCADE,
        related_name='resume'
    )

    resume_file = models.FileField(
    upload_to='resumes/',
    storage=private_resume_storage,
)

    extracted_text = models.TextField(
        blank=True
    )

    uploaded_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return f"{self.student.full_name or self.student.user.username} - Resume"
       