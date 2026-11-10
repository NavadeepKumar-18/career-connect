from django.conf import settings
from django.db import models


class Career(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    required_skills = models.CharField(max_length=500)

    def __str__(self):
        return self.title


class CareerAnalysis(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='career_analyses'
    )

    career = models.ForeignKey(
        Career,
        on_delete=models.CASCADE
    )

    match_percentage = models.PositiveIntegerField(default=0)

    matched_skills = models.TextField(blank=True)

    missing_skills = models.TextField(blank=True)

    readiness_score = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student.username} - {self.career.title}"



class CareerChatMessage(models.Model):
    ROLE_CHOICES = [
        ("user", "User"),
        ("assistant", "Assistant"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="career_chat_messages",
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.user} - {self.role}"
