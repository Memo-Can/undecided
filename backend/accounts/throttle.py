"""Failed-login throttle keyed by the attempted e-mail (no IP tracking), stored in Django's DB cache."""
import hashlib

from django.core.cache import cache

MAX_FAILS = 5
WINDOW_SECONDS = 15 * 60


def _key(email):
    return "login-fail:" + hashlib.sha256(email.strip().lower().encode()).hexdigest()


def is_locked(email):
    return cache.get(_key(email), 0) >= MAX_FAILS


def record_failure(email):
    key = _key(email)
    cache.add(key, 0, WINDOW_SECONDS)
    try:
        cache.incr(key)
    except ValueError:  # expired between add and incr
        cache.set(key, 1, WINDOW_SECONDS)


def clear(email):
    cache.delete(_key(email))
