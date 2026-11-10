"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

from dashboard import views as dashboard_views


def admin_logout_redirect(request):
    return redirect('dashboard:admin_dashboard')


urlpatterns = [
    # Custom admin logout redirect
    path('admin/logout/', admin_logout_redirect, name='admin_logout_redirect'),

    # Django admin
    path('admin/', admin.site.urls),

    # Public home page
    path('', dashboard_views.home, name='home'),

    # Application modules
    path('accounts/', include('accounts.urls')),
    path('dashboard/', include('dashboard.urls', namespace='dashboard')),
    path('students/', include('students.urls')),
    path('jobs/', include('jobs.urls')),
    path('ai-career/', include('ai_career.urls')),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )
