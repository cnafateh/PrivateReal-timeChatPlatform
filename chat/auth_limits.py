"""Shared login throttling without retaining plaintext account names."""

import hashlib
import logging

from django.conf import settings

from .monitoring import redis_client

logger = logging.getLogger(__name__)
MAX_FAILURES = 10
WINDOW_SECONDS = 15 * 60


def _key(username):
    normalized = username.strip()
    digest = hashlib.sha256(f"{settings.SECRET_KEY}:{normalized}".encode()).hexdigest()
    return f"pulse:auth:failures:{digest}"


def login_is_limited(username):
    if not username or not settings.REDIS_URL:
        return False
    try:
        return int(redis_client(settings.REDIS_URL).get(_key(username)) or 0) >= MAX_FAILURES
    except Exception:
        logger.warning("Login throttle unavailable", exc_info=True)
        return False


def note_login_failure(username):
    if not username or not settings.REDIS_URL:
        return
    try:
        client = redis_client(settings.REDIS_URL)
        key = _key(username)
        pipe = client.pipeline(transaction=True)
        pipe.incr(key)
        pipe.expire(key, WINDOW_SECONDS, nx=True)
        pipe.execute()
    except Exception:
        logger.warning("Login throttle unavailable", exc_info=True)


def clear_login_failures(username):
    if username and settings.REDIS_URL:
        try:
            redis_client(settings.REDIS_URL).delete(_key(username))
        except Exception:
            logger.warning("Login throttle unavailable", exc_info=True)
