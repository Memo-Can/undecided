from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import ensure_csrf_cookie

from .models import Poll


@ensure_csrf_cookie
def home(request):
    return render(request, "home.html")


@ensure_csrf_cookie
def poll_page(request, poll_id):
    get_object_or_404(Poll, pk=poll_id)
    return render(request, "poll.html", {"poll_id": poll_id})


@ensure_csrf_cookie
def new_poll_page(request):
    return render(request, "new.html")


@ensure_csrf_cookie
def login_page(request):
    return render(request, "login.html")


@ensure_csrf_cookie
def register_page(request):
    return render(request, "register.html")
