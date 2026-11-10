from django.contrib import admin
from .models import Company, Job, Application,Notification


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = (
        'company_name',
        'recruiter',
        'location',
        'is_approved',
        'created_at'
    )

    list_filter = (
        'is_approved',
        'created_at'
    )

    search_fields = (
        'company_name',
        'location',
        'recruiter__username',
        'recruiter__email'
    )

    list_editable = ('is_approved',)


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'company',
        'location',
        'minimum_cgpa',
        'deadline',
        'is_active',
        'created_at'
    )

    list_filter = (
        'is_active',
        'deadline',
        'created_at'
    )

    search_fields = (
        'title',
        'company__company_name',
        'required_skills',
        'location'
    )

    list_editable = ('is_active',)


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = (
        'student',
        'job',
        'status',
        'applied_at'
    )

    list_filter = (
        'status',
        'applied_at'
    )

    search_fields = (
        'student__full_name',
        'student__user__username',
        'job__title',
        'job__company__company_name'
    )

    list_editable = ('status',)

    readonly_fields = ('applied_at',)

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'student',
        'application',
        'is_read',
        'created_at',
    )
    list_filter = ('is_read', 'created_at')
    search_fields = (
        'student__full_name',
        'student__user__username',
        'title',
        'message',
    )
    readonly_fields = ('created_at',)