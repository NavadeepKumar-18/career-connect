
from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model


PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
]


@override_settings(AUTH_PASSWORD_VALIDATORS=PASSWORD_VALIDATORS)
class RegistrationSecurityTests(TestCase):

    def test_student_registration_rejects_weak_password(self):
        response = self.client.post(
            reverse("student_register"),
            {
                "username": "weak_student",
                "email": "weak@example.com",
                "password": "weak",
                "confirm_password": "weak",
            },
        )

        self.assertFalse(
            get_user_model().objects.filter(
                username="weak_student"
            ).exists()
        )

    def test_student_registration_accepts_strong_password(self):
        response = self.client.post(
            reverse("student_register"),
            {
                "username": "strong_student",
                "email": "strong@example.com",
                "password": "Strong-Pass-2026!",
                "confirm_password": "Strong-Pass-2026!",
            },
        )

        self.assertTrue(
            get_user_model().objects.filter(
                username="strong_student",
                role="STUDENT",
            ).exists()
        )

    def test_recruiter_registration_rejects_weak_password(self):
        self.client.post(
            reverse("recruiter_register"),
            {
                "username": "weak_recruiter",
                "email": "weak_recruiter@example.com",
                "password": "weak",
                "confirm_password": "weak",
            },
        )

        self.assertFalse(
            get_user_model().objects.filter(
                username="weak_recruiter"
            ).exists()
        )

    def test_recruiter_registration_accepts_strong_password(self):
        self.client.post(
            reverse("recruiter_register"),
            {
                "username": "strong_recruiter",
                "email": "strong_recruiter@example.com",
                "password": "Strong-Pass-2026!",
                "confirm_password": "Strong-Pass-2026!",
            },
        )

        recruiter = get_user_model().objects.filter(
            username="strong_recruiter",
            role="RECRUITER",
        ).first()

        self.assertIsNotNone(recruiter)

        if recruiter:
            self.assertFalse(recruiter.is_recruiter_approved)


class LogoutSecurityTests(TestCase):

    def test_logout_rejects_get_request(self):
        User = get_user_model()

        user = User.objects.create_user(
            username="logout_test",
            password="Test-password-123!",
            role="STUDENT",
        )

        self.client.force_login(user)

        response = self.client.get(reverse("logout"))

        self.assertEqual(response.status_code, 405)

    def test_logout_accepts_post_request(self):
        User = get_user_model()

        user = User.objects.create_user(
            username="logout_post_test",
            password="Test-password-123!",
            role="STUDENT",
        )

        self.client.force_login(user)

        response = self.client.post(reverse("logout"))

        self.assertEqual(response.status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)
