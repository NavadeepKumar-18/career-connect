
from django.core.management.base import BaseCommand
from django.utils import timezone

from jobs.models import Job


class Command(BaseCommand):
    help = "Deactivate jobs whose application deadline has passed."

    def handle(self, *args, **options):
        today = timezone.localdate()

        expired_jobs = Job.objects.filter(
            is_active=True,
            deadline__lt=today,
        )

        count = expired_jobs.update(is_active=False)

        self.stdout.write(
            self.style.SUCCESS(
                f"Deactivated {count} expired job(s)."
            )
        )
