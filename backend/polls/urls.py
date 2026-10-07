from django.urls import path

from . import views_api

urlpatterns = [
    path("", views_api.poll_list),
    path("<int:poll_id>/", views_api.poll_detail),
    path("<int:poll_id>/vote/", views_api.vote),
]
