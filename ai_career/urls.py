from django.urls import path
from . import views


urlpatterns = [

    # path(
    #     'career-recommendation/',
    #     views.career_recommendation,
    #     name='career_recommendation'
    # ),

    path(
        'recommended-jobs/',
        views.recommended_jobs,
        name='recommended_jobs'
    ),

    path(
    'career-readiness/',
    views.career_readiness,
    name='career_readiness'
),
       path(
        'career-assistant/',
        views.career_assistant,
        name='career_assistant'
    ),
    path(
    "copilot/chat/",
    views.career_copilot_api,
    name="career_copilot_api",
),
path(
    "copilot/",
    views.career_copilot_page,
    name="career_copilot_page",
),
path('career_recommendation/',views.career_recommendation,name='career_recommendation'),
]