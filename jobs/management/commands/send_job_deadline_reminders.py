
import logging
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.urls import reverse
from django.utils import timezone

from students.models import StudentProfile
from jobs.models import Job, Application, Notification
from jobs.views import is_branch_eligible


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Send in-app and email reminders for approaching job deadlines."

    def handle(self, *args, **options):
        today = timezone.localdate()

        reminder_days = {
            3: "3_DAYS",
            1: "1_DAY",
            0: "DUE_TODAY",
        }

        notifications_created = 0
        emails_sent = 0

        jobs = Job.objects.filter(
            is_active=True,
            deadline__in=[
                today,
                today + timedelta(days=1),
                today + timedelta(days=3),
            ],
            company__is_approved=True,
            company__recruiter__is_recruiter_approved=True,
        ).select_related(
            "company",
            "company__recruiter",
        )

        for job in jobs:
            days_left = (job.deadline - today).days
            reminder_type = reminder_days.get(days_left)

            if not reminder_type:
                continue

            applied_student_ids = Application.objects.filter(
                job=job
            ).values_list("student_id", flat=True)

            students = StudentProfile.objects.select_related(
                "user"
            ).exclude(
                id__in=applied_student_ids
            )

            for student in students:
                # Check branch eligibility.
                if not is_branch_eligible(
                    student.branch,
                    job.eligible_branches
                ):
                    continue

                # Exclude students whose known CGPA is below the requirement.
                if (
                    student.cgpa is not None
                    and student.cgpa < job.minimum_cgpa
                ):
                    continue

                if days_left == 3:
                    title = "Job deadline in 3 days"
                    message = (
                        f"The application deadline for {job.title} "
                        f"at {job.company.company_name} is in 3 days. "
                        "Apply soon!"
                    )
                elif days_left == 1:
                    title = "Job deadline tomorrow"
                    message = (
                        f"The application deadline for {job.title} "
                        f"at {job.company.company_name} is tomorrow. "
                        "Don't miss this opportunity!"
                    )
                else:
                    title = "Job application closes today"
                    message = (
                        f"Today is the last day to apply for {job.title} "
                        f"at {job.company.company_name}. Apply now!"
                    )

                notification, created = Notification.objects.get_or_create(
                    student=student,
                    job=job,
                    reminder_type=reminder_type,
                    defaults={
                        "title": title,
                        "message": message,
                    },
                )

                if created:
                    notifications_created += 1

                # Send email only if it has not already been sent.
                email = student.user.email

                if notification.email_sent or not email:
                    continue

                try:
                    site_url = getattr(
                        settings,
                        "SITE_URL",
                        "https://smart-career-placement-system.vercel.app",
                    ).rstrip("/")

                    job_url = (
                        f"{site_url}{reverse('job_detail', args=[job.id])}"
                    )

                    subject = title

                    email_message = (
                        f"Hello {student.full_name},\n\n"
                        f"{message}\n\n"
                        f"Job: {job.title}\n"
                        f"Company: {job.company.company_name}\n"
                        f"Deadline: {job.deadline.strftime('%d-%m-%Y')}\n\n"
                        f"Apply here:\n{job_url}\n\n"
                        "Log in to your Career Connect Platform"
                        "account to apply.\n\n"
                        "Best regards,\n"
                        "Career Connect Team"
                    )

                    result = send_mail(
                        subject,
                        email_message,
                        settings.DEFAULT_FROM_EMAIL,
                        [email],
                        fail_silently=False,
                    )

                    if result == 1:
                        notification.email_sent = True
                        notification.save(update_fields=["email_sent"])
                        emails_sent += 1

                except Exception:
                    logger.exception(
                        "Failed to send deadline reminder to %s",
                        email,
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f"Deadline reminder process completed. "
                f"New notifications: {notifications_created}. "
                f"Emails sent: {emails_sent}."
            )
        )
