from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):

    STUDENT = 'STUDENT'
    RECRUITER = 'RECRUITER'
    ADMIN = 'ADMIN'

    ROLE_CHOICES = [
        (STUDENT, 'Student'),
        (RECRUITER, 'Recruiter'),
        (ADMIN, 'Admin'),
    ]

    email = models.EmailField(unique=True)

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=STUDENT
    )

    # Admin must approve a recruiter before company registration.
    is_recruiter_approved = models.BooleanField(default=False)

    def __str__(self):
        return self.username
