from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from polls import views

urlpatterns = [
    path("api/auth/", include("accounts.urls")),
    path("api/polls/", include("polls.urls")),
    path("", views.home, name="home"),
    path("anket/<int:poll_id>/", views.poll_page, name="poll"),
    path("yeni/", views.new_poll_page, name="new"),
    path("giris/", views.login_page, name="login"),
    path("kayit/", views.register_page, name="register"),
]

if settings.ENABLE_ADMIN:
    urlpatterns.append(path("admin/", admin.site.urls))
