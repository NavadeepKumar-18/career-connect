from django.contrib import admin

from .models import StudentProfile, StudentSkill,Project,Resume


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):

    list_display = (
        'full_name',
        'branch',
        'college',
        'cgpa',
        'career_interest',
    )

    search_fields = (
        'full_name',
        'college',
        'branch',
    )


@admin.register(StudentSkill)
class StudentSkillAdmin(admin.ModelAdmin):

    list_display = (
        'student',
        'skill',
        'proficiency',
    )

    list_filter = (
        'proficiency',
    )

    search_fields = (
        'skill',
        'student__full_name',
    )

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):

    list_display = (
        'title',
        'student',
        'technologies',
        'created_at',
    )

    search_fields = (
        'title',
        'technologies',
        'student__full_name',
    )

@admin.register(Resume)
class ResumeAdmin(admin.ModelAdmin):

    list_display = (
        'student',
        'resume_file',
        'uploaded_at',
    )

    search_fields = (
        'student__full_name',
        'student__user__username',
    )

    readonly_fields = (
        'uploaded_at',
    )