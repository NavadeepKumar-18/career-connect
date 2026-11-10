
from django.conf import settings
from django.core.files.storage import FileSystemStorage


def private_resume_storage():
    """
    Store resumes outside the publicly accessible media directory.
    """
    return FileSystemStorage(
        location=settings.BASE_DIR / "private_media"
    )
