from django.contrib import admin
from django.urls import include, path

from polls.views import home

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/polls/", include("polls.urls")),
    path("", home, name="home"),
]
