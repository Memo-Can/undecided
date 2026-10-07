import json
import re

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods, require_POST

from .models import User

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")


def read_json(request):
    try:
        data = json.loads(request.body or b"{}")
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def user_payload(user):
    return {"id": user.id, "username": user.username, "email": user.email}


def clean_str(data, key):
    value = data.get(key)
    return value.strip() if isinstance(value, str) else ""


@require_POST
def register(request):
    data = read_json(request)
    email = clean_str(data, "email")
    username = clean_str(data, "username")
    password = data.get("password") if isinstance(data.get("password"), str) else ""
    errors = {}

    try:
        validate_email(email)
        if User.objects.filter(email__iexact=email).exists():
            errors["email"] = ["Bu e-posta adresi zaten kayıtlı."]
    except ValidationError:
        errors["email"] = ["Geçerli bir e-posta adresi gir."]

    if not USERNAME_RE.match(username):
        errors["username"] = ["Kullanıcı adı 3-20 karakter olmalı; yalnızca harf, rakam ve _ kullanılabilir."]
    elif User.objects.filter(username__iexact=username).exists():
        errors["username"] = ["Bu kullanıcı adı alınmış."]

    if not password:
        errors["password"] = ["Parola zorunludur."]
    else:
        try:
            validate_password(password, User(username=username, email=email))
        except ValidationError as exc:
            errors["password"] = list(exc.messages)

    if errors:
        return JsonResponse({"errors": errors}, status=400)

    user = User.objects.create_user(username=username, email=email, password=password)
    login(request, user)
    return JsonResponse({"user": user_payload(user)}, status=201)


@require_POST
def login_view(request):
    data = read_json(request)
    email = clean_str(data, "email")
    password = data.get("password") if isinstance(data.get("password"), str) else ""
    found = User.objects.filter(email__iexact=email).first() if email else None
    user = authenticate(request, username=found.username, password=password) if found else None
    if user is None:
        return JsonResponse({"errors": {"__all__": ["E-posta veya parola hatalı."]}}, status=400)
    login(request, user)
    return JsonResponse({"user": user_payload(user)})


@require_POST
def logout_view(request):
    if not request.user.is_authenticated:
        return JsonResponse({"errors": {"__all__": ["Giriş yapmalısın."]}}, status=401)
    logout(request)
    return JsonResponse({"ok": True})


@ensure_csrf_cookie
@require_http_methods(["GET"])
def me(request):
    user = request.user
    return JsonResponse({"user": user_payload(user) if user.is_authenticated else None})
