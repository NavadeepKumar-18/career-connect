from django.contrib import admin
from .models import Career, CareerAnalysis


@admin.register(Career)
class CareerAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'required_skills',
    )

    search_fields = (
        'title',
        'required_skills',
    )


@admin.register(CareerAnalysis)
class CareerAnalysisAdmin(admin.ModelAdmin):
    list_display = (
        'student',
        'career',
        'match_percentage',
        'readiness_score',
        'created_at',
    )

    list_filter = (
        'career',
        'created_at',
    )