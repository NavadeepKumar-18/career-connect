
import secrets
import logging

from django.conf import settings
from django.core.management import call_command
from django.http import JsonResponse
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)


@require_GET
def send_deadline_reminders(request):
    expected_secret = getattr(settings, "CRON_SECRET", "")
    authorization = request.headers.get("Authorization", "")

    if (
        not expected_secret
        or not secrets.compare_digest(
            authorization,
            f"Bearer {expected_secret}"
        )
    ):
        return JsonResponse(
            {"error": "Unauthorized"},
            status=403
        )

    try:
        call_command("send_job_deadline_reminders")

        return JsonResponse({
            "status": "success",
            "message": "Deadline reminders processed successfully."
        })

    except Exception:
        logger.exception("Deadline reminder cron execution failed.")

        return JsonResponse(
            {"status": "error", "message": "Reminder processing failed."},
            status=500
        )
