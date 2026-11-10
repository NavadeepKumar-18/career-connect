
from unittest.mock import patch

from django.test import TestCase, SimpleTestCase
from django.contrib.auth import get_user_model
from types import SimpleNamespace

from students.models import StudentProfile
from ai_career.services import (
    normalize_skill,
    normalize_resume_text,
    calculate_job_match,
    is_branch_eligible,
)


class SkillNormalizationTests(SimpleTestCase):

    def test_skill_aliases(self):
        cases = {
            "HTML5": "html",
            "CSS3": "css",
            "Python3": "python",
            "Python 3": "python",
            "JS": "javascript",
            "Django Framework": "django",
            "PostgreSQL DB": "postgresql",
            "ReactJS": "react",
        }

        for original, expected in cases.items():
            with self.subTest(original=original):
                self.assertEqual(
                    normalize_skill(original),
                    expected,
                )

    def test_resume_text_aliases(self):
        resume = (
            "Experienced in HTML5, CSS3, Python3, "
            "JS, Django Framework and ReactJS."
        )

        normalized = normalize_resume_text(resume)

        self.assertIn("html", normalized)
        self.assertIn("css", normalized)
        self.assertIn("python", normalized)
        self.assertIn("javascript", normalized)
        self.assertIn("django", normalized)
        self.assertIn("react", normalized)

    def test_empty_skill_returns_empty_string(self):
        self.assertEqual(normalize_skill(""), "")


class BranchEligibilityTests(SimpleTestCase):

    def test_branch_aliases_are_equivalent(self):
        self.assertTrue(
            is_branch_eligible(
                "Computer Science Engineering",
                ["CSE"],
            )
        )

    def test_wrong_branch_is_rejected(self):
        self.assertFalse(
            is_branch_eligible(
                "ECE",
                ["CSE"],
            )
        )

    def test_empty_branch_list_allows_all_branches(self):
        self.assertTrue(
            is_branch_eligible("ECE", [])
        )


class ResumeJobMatchingTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username="matching_student",
            password="Test-password-123!",
            role="STUDENT",
        )

        self.profile = StudentProfile.objects.create(
            user=self.user,
            full_name="Matching Student",
            branch="CSE",
            cgpa=8.50,
        )

    @patch(
        "ai_career.services.get_student_skill_evidence",
        return_value=(
            set(),
            "Experienced in HTML5 and Python3.",
        ),
    )
    def test_resume_aliases_match_required_job_skills(self, mock_evidence):
        job = SimpleNamespace(
            required_skills="HTML, Python",
            required_soft_skills="",
        )

        result = calculate_job_match(self.profile, job)

        self.assertEqual(result["match_percentage"], 100)
        self.assertEqual(
            set(result["matched_skills"]),
            {"html", "python"},
        )
        self.assertEqual(result["missing_skills"], [])
