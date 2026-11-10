from datetime import timedelta
from decimal import Decimal
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile

from jobs.models import Notification
from students.models import Resume
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from jobs.models import Application, Company, Job
from students.models import StudentProfile


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class JobApplicationWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.student_user = User.objects.create_user(
            username='student_test',
            email='student@example.com',
            password='test-password-123',
            role='STUDENT',
        )
        cls.recruiter_user = User.objects.create_user(
            username='recruiter_test',
            email='recruiter@example.com',
            password='test-password-123',
            role='RECRUITER',
            is_recruiter_approved=True,
        )
        cls.profile = StudentProfile.objects.create(
            user=cls.student_user,
            full_name='Test Student',
            branch='CSE',
            cgpa=Decimal('8.50'),
        )
        cls.company = Company.objects.create(
            recruiter=cls.recruiter_user,
            company_name='Test Company',
            is_approved=True,
        )

    def make_job(self, **overrides):
        values = {
            'company': self.company,
            'title': 'Junior Developer',
            'description': 'A test role',
            'required_skills': 'Python, Django',
            'eligible_branches': ['CSE'],
            'minimum_cgpa': Decimal('7.00'),
            'deadline': timezone.localdate() + timedelta(days=5),
            'is_active': True,
        }
        values.update(overrides)
        return Job.objects.create(**values)

    def apply(self, job):
        self.client.force_login(self.student_user)
        return self.client.post(reverse('apply_job', args=[job.pk]))

    def test_eligible_student_can_apply_once(self):
        job = self.make_job()

        response = self.apply(job)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Application.objects.filter(student=self.profile, job=job).exists()
        )

    def test_student_cannot_apply_to_wrong_branch(self):
        job = self.make_job(eligible_branches=['MECHANICAL'])

        self.apply(job)

        self.assertFalse(
            Application.objects.filter(student=self.profile, job=job).exists()
        )

    def test_student_cannot_apply_below_minimum_cgpa(self):
        job = self.make_job(minimum_cgpa=Decimal('9.00'))

        self.apply(job)

        self.assertFalse(
            Application.objects.filter(student=self.profile, job=job).exists()
        )

    def test_student_cannot_apply_after_deadline(self):
        job = self.make_job(deadline=timezone.localdate() - timedelta(days=1))

        self.apply(job)

        self.assertFalse(
            Application.objects.filter(student=self.profile, job=job).exists()
        )

    def test_duplicate_application_is_not_created(self):
        job = self.make_job()
        Application.objects.create(student=self.profile, job=job)

        self.apply(job)

        self.assertEqual(
            Application.objects.filter(student=self.profile, job=job).count(), 1
        )

    def test_get_request_cannot_submit_application(self):
        job = self.make_job()
        self.client.force_login(self.student_user)

        response = self.client.get(reverse('apply_job', args=[job.pk]))

        self.assertEqual(response.status_code, 405)
        self.assertFalse(
            Application.objects.filter(student=self.profile, job=job).exists()
        )

@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
)
class RecruiterApplicationWorkflowTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()

        cls.student_user = User.objects.create_user(
            username='applicant_test',
            email='applicant@example.com',
            password='test-password-123',
            role='STUDENT'
        )

        cls.recruiter_user = User.objects.create_user(
            username='company_recruiter',
            email='recruiter@example.com',
            password='test-password-123',
            role='RECRUITER',
            is_recruiter_approved=True
        )

        cls.profile = StudentProfile.objects.create(
            user=cls.student_user,
            full_name='Test Applicant',
            branch='CSE',
            college='Test Polytechnic College',
            phone='9876543210',
            cgpa=Decimal('8.50'),
            career_interest='Python Developer'
        )

        cls.company = Company.objects.create(
            recruiter=cls.recruiter_user,
            company_name='Test Recruitment Company',
            is_approved=True
        )

        cls.job = Job.objects.create(
            company=cls.company,
            title='Python Developer',
            description='Test job description',
            required_skills='Python, Django',
            eligible_branches=['CSE'],
            minimum_cgpa=Decimal('7.00'),
            deadline=timezone.localdate() + timedelta(days=5)
        )

        cls.application = Application.objects.create(
            student=cls.profile,
            job=cls.job
        )

    def setUp(self):
        self.client.force_login(self.recruiter_user)

    def test_recruiter_can_view_applications(self):
        response = self.client.get(
            reverse('recruiter_applications')
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Applicant')
        self.assertContains(response, 'Test Polytechnic College')

    def test_status_update_creates_notification_and_email(self):
        response = self.client.post(
            reverse(
                'update_application_status',
                args=[self.application.pk]
            ),
            {'status': Application.SHORTLISTED}
        )

        self.assertEqual(response.status_code, 302)

        self.application.refresh_from_db()

        self.assertEqual(
            self.application.status,
            Application.SHORTLISTED
        )

        self.assertEqual(
            Notification.objects.filter(
                application=self.application
            ).count(),
            1
        )

        self.assertEqual(len(mail.outbox), 1)

    def test_same_status_does_not_create_duplicate_notification(self):
        response = self.client.post(
            reverse(
                'update_application_status',
                args=[self.application.pk]
            ),
            {'status': Application.APPLIED}
        )

        self.assertEqual(response.status_code, 302)

        self.assertEqual(
            Notification.objects.filter(
                application=self.application
            ).count(),
            0
        )

        self.assertEqual(len(mail.outbox), 0)

    def test_invalid_status_is_rejected(self):
        self.client.post(
            reverse(
                'update_application_status',
                args=[self.application.pk]
            ),
            {'status': 'INVALID_STATUS'}
        )

        self.application.refresh_from_db()

        self.assertEqual(
            self.application.status,
            Application.APPLIED
        )

    def test_recruiter_can_download_applicant_resume(self):
        Resume.objects.create(
            student=self.profile,
            resume_file=SimpleUploadedFile(
                'test_resume.pdf',
                b'%PDF-1.4 test resume content',
                content_type='application/pdf'
            )
        )

        response = self.client.get(
            reverse(
                'recruiter_application_resume',
                args=[self.application.pk]
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            'attachment;',
            response['Content-Disposition']
        )

        response.close()

    def test_other_recruiter_cannot_access_application(self):
        User = get_user_model()

        another_recruiter = User.objects.create_user(
            username='another_recruiter',
            password='test-password-123',
            role='RECRUITER',
            is_recruiter_approved=True
        )

        Company.objects.create(
            recruiter=another_recruiter,
            company_name='Another Company',
            is_approved=True
        )

        self.client.force_login(another_recruiter)

        response = self.client.get(
            reverse(
                'recruiter_application_resume',
                args=[self.application.pk]
            )
        )

        self.assertEqual(response.status_code, 404)
