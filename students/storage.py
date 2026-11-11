
import os
import uuid
from io import BytesIO
from django.conf import settings
import cloudinary
import cloudinary.uploader
from cloudinary.utils import private_download_url
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible
from django.utils import timezone
import requests

cloudinary.config(
    cloud_name=settings.CLOUDINARY_STORAGE["CLOUD_NAME"],
    api_key=settings.CLOUDINARY_STORAGE["API_KEY"],
    api_secret=settings.CLOUDINARY_STORAGE["API_SECRET"],
    secure=True,
)
@deconstructible
class PrivateResumeStorage(Storage):

    def _save(self, name, content):
        extension = os.path.splitext(name)[1].lower()

        public_id = f"resumes/{uuid.uuid4().hex}{extension}"

        result = cloudinary.uploader.upload(
            content,
            resource_type="raw",
            type="authenticated",
            public_id=public_id,
        )

        return result["public_id"]

    def _open(self, name, mode="rb"):
        extension = os.path.splitext(name)[1].lstrip(".").lower()

        url = private_download_url(
            name,
            extension,
            resource_type="raw",
            type="authenticated",
            expires_at=int(timezone.now().timestamp()) + 300,
        )

        response = requests.get(url, timeout=30)
        response.raise_for_status()

        return ContentFile(response.content, name=os.path.basename(name))

    def delete(self, name):
        cloudinary.uploader.destroy(
            name,
            resource_type="raw",
            type="authenticated",
        )

    def exists(self, name):
        return False

    def url(self, name):
        raise NotImplementedError(
            "Private resumes must be accessed through authorized Django views."
        )


private_resume_storage = PrivateResumeStorage()
