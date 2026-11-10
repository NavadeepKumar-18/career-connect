
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from students.models import StudentProfile, StudentSkill, Project, Resume


class StudentSecurityTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()

        cls.student = User.objects.create_user(
            username="security_student",
            email="security_student@example.com",
            password="Test-password-123!",
            role="STUDENT",
        )

        cls.other_student = User.objects.create_user(
            username="other_student",
            email="other_student@example.com",
            password="Test-password-123!",
            role="STUDENT",
        )

        cls.recruiter = User.objects.create_user(
            username="security_recruiter",
            email="security_recruiter@example.com",
            password="Test-password-123!",
            role="RECRUITER",
            is_recruiter_approved=True,
        )

        cls.admin = User.objects.create_user(
            username="security_admin",
            email="security_admin@example.com",
            password="Test-password-123!",
            role="ADMIN",
        )

        cls.profile = StudentProfile.objects.create(
            user=cls.student,
            full_name="Security Student",
            branch="CSE",
            cgpa=8.50,
        )

        cls.other_profile = StudentProfile.objects.create(
            user=cls.other_student,
            full_name="Other Student",
            branch="CSE",
            cgpa=8.00,
        )

    def test_student_can_download_own_resume(self):
        resume = Resume.objects.create(
            student=self.profile,
            resume_file=SimpleUploadedFile(
                "owner_resume.pdf",
                b"%PDF-1.4 test content",
                content_type="application/pdf",
            ),
        )

        self.client.force_login(self.student)

        response = self.client.get(
            reverse("student_resume_download", args=[resume.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        response.close()
        resume.resume_file.delete(save=False)

    def test_other_student_cannot_download_resume(self):
        resume = Resume.objects.create(
            student=self.profile,
            resume_file=SimpleUploadedFile(
                "private_resume.pdf",
                b"%PDF-1.4 test content",
                content_type="application/pdf",
            ),
        )

        self.client.force_login(self.other_student)

        response = self.client.get(
            reverse("student_resume_download", args=[resume.pk])
        )

        self.assertEqual(response.status_code, 403)
        resume.resume_file.delete(save=False)

    def test_recruiter_cannot_use_student_resume_download(self):
        resume = Resume.objects.create(
            student=self.profile,
            resume_file=SimpleUploadedFile(
                "recruiter_test.pdf",
                b"%PDF-1.4 test content",
                content_type="application/pdf",
            ),
        )

        self.client.force_login(self.recruiter)

        response = self.client.get(
            reverse("student_resume_download", args=[resume.pk])
        )

        self.assertEqual(response.status_code, 403)
        resume.resume_file.delete(save=False)

    def test_admin_can_download_student_resume(self):
        resume = Resume.objects.create(
            student=self.profile,
            resume_file=SimpleUploadedFile(
                "admin_test.pdf",
                b"%PDF-1.4 test content",
                content_type="application/pdf",
            ),
        )

        self.client.force_login(self.admin)

        response = self.client.get(
            reverse("student_resume_download", args=[resume.pk])
        )

        self.assertEqual(response.status_code, 200)
        response.close()
        resume.resume_file.delete(save=False)

    def test_resume_download_requires_get(self):
        resume = Resume.objects.create(
            student=self.profile,
            resume_file=SimpleUploadedFile(
                "method_test.pdf",
                b"%PDF-1.4 test content",
                content_type="application/pdf",
            ),
        )

        self.client.force_login(self.student)

        response = self.client.post(
            reverse("student_resume_download", args=[resume.pk])
        )

        self.assertEqual(response.status_code, 405)
        resume.resume_file.delete(save=False)

    def test_skill_deletion_rejects_get(self):
        skill = StudentSkill.objects.create(
            student=self.profile,
            skill="Python",
            proficiency="BEGINNER",
            skill_type="TECHNICAL",
        )

        self.client.force_login(self.student)

        response = self.client.get(
            reverse("delete_skill", args=[skill.pk])
        )

        self.assertEqual(response.status_code, 405)
        self.assertTrue(StudentSkill.objects.filter(pk=skill.pk).exists())

    def test_skill_deletion_accepts_post(self):
        skill = StudentSkill.objects.create(
            student=self.profile,
            skill="Python",
            proficiency="BEGINNER",
            skill_type="TECHNICAL",
        )

        self.client.force_login(self.student)

        response = self.client.post(
            reverse("delete_skill", args=[skill.pk])
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(StudentSkill.objects.filter(pk=skill.pk).exists())

    def test_project_deletion_rejects_get(self):
        project = Project.objects.create(
            student=self.profile,
            title="Test Project",
            description="Project description",
            technologies="Python, Django",
        )

        self.client.force_login(self.student)

        response = self.client.get(
            reverse("delete_project", args=[project.pk])
        )

        self.assertEqual(response.status_code, 405)
        self.assertTrue(Project.objects.filter(pk=project.pk).exists())

    def test_project_deletion_accepts_post(self):
        project = Project.objects.create(
            student=self.profile,
            title="Test Project",
            description="Project description",
            technologies="Python, Django",
        )

        self.client.force_login(self.student)

        response = self.client.post(
            reverse("delete_project", args=[project.pk])
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Project.objects.filter(pk=project.pk).exists())

    def test_resume_deletion_rejects_get(self):
        resume = Resume.objects.create(
            student=self.profile,
            resume_file=SimpleUploadedFile(
                "delete_test.pdf",
                b"%PDF-1.4 test content",
                content_type="application/pdf",
            ),
        )

        self.client.force_login(self.student)

        response = self.client.get(reverse("delete_resume"))

        self.assertEqual(response.status_code, 405)
        self.assertTrue(Resume.objects.filter(pk=resume.pk).exists())
        resume.resume_file.delete(save=False)

    def test_resume_deletion_accepts_post(self):
        resume = Resume.objects.create(
            student=self.profile,
            resume_file=SimpleUploadedFile(
                "delete_post_test.pdf",
                b"%PDF-1.4 test content",
                content_type="application/pdf",
            ),
        )

        self.client.force_login(self.student)

        response = self.client.post(reverse("delete_resume"))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Resume.objects.filter(pk=resume.pk).exists())
