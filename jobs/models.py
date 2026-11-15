from django.conf import settings
from django.db import models


class Company(models.Model):

    recruiter = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='company'
    )

    company_name = models.CharField(
        max_length=200
    )

    description = models.TextField(
        blank=True
    )

    website = models.URLField(
        blank=True
    )

    location = models.CharField(
        max_length=200,
        blank=True
    )

    is_approved = models.BooleanField(
        default=False
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return self.company_name


class Job(models.Model):

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='jobs'
    )

    title = models.CharField(
        max_length=200
    )

    description = models.TextField()

    required_skills = models.CharField(
        max_length=500
    )
    required_soft_skills = models.CharField(
    max_length=500,
    blank=True,
    help_text="Required soft skills separated by commas."
)
    eligible_branches = models.JSONField(
        default=list,
        blank=True,
        help_text="Branches eligible for this job. An empty list means all branches."
    )
    minimum_cgpa = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True
    )

    location = models.CharField(
        max_length=200,
        blank=True
    )

    salary = models.CharField(
        max_length=100,
        blank=True
    )

    deadline = models.DateField()

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    is_active = models.BooleanField(
        default=True
    )

    def __str__(self):
        return self.title

class Application(models.Model):
    APPLIED = 'APPLIED'
    SHORTLISTED = 'SHORTLISTED'
    INTERVIEW_SCHEDULED = 'INTERVIEW_SCHEDULED'
    REJECTED = 'REJECTED'
    SELECTED = 'SELECTED'

    STATUS_CHOICES = [
    (APPLIED, 'Applied'),
    (SHORTLISTED, 'Shortlisted'),
    (INTERVIEW_SCHEDULED, 'Interview Scheduled'),
    (REJECTED, 'Rejected'),
    (SELECTED, 'Selected'),
]

    student = models.ForeignKey(
        'students.StudentProfile',
        on_delete=models.CASCADE,
        related_name='applications'
    )

    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name='applications'
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=APPLIED
    )

    applied_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'job'],
                name='unique_student_job_application'
            )
        ]

    def __str__(self):
        return f"{self.student} - {self.job.title}"


class Notification(models.Model):
    student = models.ForeignKey(
        'students.StudentProfile',
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    application = models.ForeignKey(
    Application,
    on_delete=models.CASCADE,
    null=True,
    blank=True
)
    job = models.ForeignKey(
    Job,
    on_delete=models.CASCADE,
    null=True,
    blank=True,
    related_name="notifications"
)
    reminder_type = models.CharField(
    max_length=20,
    blank=True,
    default=""
)

    email_sent = models.BooleanField(default=False)
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
       ordering = ['-created_at']

       constraints = [
        models.UniqueConstraint(
            fields=['student', 'job', 'reminder_type'],
            condition=~models.Q(reminder_type=''),
            name='unique_student_job_deadline_reminder'
        )
    ]

    def __str__(self):
        return f"{self.title} - {self.student}"