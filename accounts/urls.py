from django.urls import path
from . import views


urlpatterns = [
    path('register/student/', views.student_register, name='student_register'),
    path('register/recruiter/', views.recruiter_register, name='recruiter_register'),

    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
]