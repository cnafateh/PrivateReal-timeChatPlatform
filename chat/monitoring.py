"""Anonymous operational counters and a private status dashboard."""

import json
import logging
import os
import shutil
import tempfile
import time
from datetime import timedelta
from functools import lru_cache

from django.conf import settings
from django.contrib.auth.models import User
from django.db import connection
from django.http import HttpResponseForbidden
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from .models import GroupChat, Message, PrivateChat

logger = logging.getLogger(__name__)
PREFIX = "pulse:monitor:v1"
_metrics_retry_after = 0.0


@lru_cache(maxsize=4)
def redis_client(url):
    import redis
    return redis.Redis.from_url(url, socket_connect_timeout=0.3, socket_timeout=0.3)


def record_request(route, status, elapsed_ms, now=None):
    """Store only aggregate HTTP counters and named routes, never paths or users."""
    global _metrics_retry_after
    if not settings.REDIS_URL or not route or route == "monitor" or time.monotonic() < _metrics_retry_after:
        return
    now = now or timezone.now()
    key = f"{PREFIX}:hour:{now.strftime('%Y%m%d%H')}"
    try:
        pipe = redis_client(settings.REDIS_URL).pipeline(transaction=False)
        pipe.hincrby(key, "requests", 1)
        pipe.hincrby(key, f"{status // 100}xx", 1)
        pipe.hincrby(key, "latency_ms", min(max(int(elapsed_ms), 0), 120000))
        pipe.expire(key, 172800)
        if status >= 500:
            event_key = f"{PREFIX}:errors"
            pipe.lpush(event_key, json.dumps({"at": now.isoformat(), "route": route, "status": status}))
            pipe.ltrim(event_key, 0, 19)
            pipe.expire(event_key, 172800)
        pipe.execute()
    except Exception:
        _metrics_retry_after = time.monotonic() + 30
        logger.warning("Operational counters are unavailable", exc_info=True)


class RequestMetricsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started = time.monotonic()
        response = self.get_response(request)
        match = getattr(request, "resolver_match", None)
        record_request(getattr(match, "url_name", None) or "unmatched", response.status_code,
                       (time.monotonic() - started) * 1000)
        return response


def operational_snapshot(now=None):
    now = now or timezone.now()
    checks = {}
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        checks["Database"] = {"ok": True, "detail": "Connected"}
    except Exception:
        checks["Database"] = {"ok": False, "detail": "Unavailable"}

    client = None
    if settings.REDIS_URL:
        try:
            client = redis_client(settings.REDIS_URL)
            client.ping()
            checks["Redis"] = {"ok": True, "detail": "Connected"}
        except Exception:
            checks["Redis"] = {"ok": False, "detail": "Unavailable"}
    else:
        checks["Redis"] = {"ok": False, "detail": "Not configured"}

    try:
        media = settings.MEDIA_ROOT
        os.makedirs(media, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=media, prefix=".monitor-", delete=True) as stream:
            stream.write(b"ok")
        disk = shutil.disk_usage(media)
        checks["Media storage"] = {"ok": True, "detail": f"{disk.free // (1024 ** 3)} GiB free"}
    except Exception:
        checks["Media storage"] = {"ok": False, "detail": "Not writable"}

    hours = [now - timedelta(hours=23 - index) for index in range(24)]
    traffic, errors = [], []
    if client:
        try:
            pipe = client.pipeline(transaction=False)
            for hour in hours:
                pipe.hgetall(f"{PREFIX}:hour:{hour.strftime('%Y%m%d%H')}")
            pipe.lrange(f"{PREFIX}:errors", 0, 19)
            values = pipe.execute()
            for hour, raw in zip(hours, values[:-1]):
                def get(field):
                    return int(raw.get(field.encode(), 0))
                count = get("requests")
                traffic.append({"hour": timezone.localtime(hour).strftime("%H:%M"),
                                "requests": count, "failures": get("5xx"),
                                "client_errors": get("4xx"),
                                "average_ms": round(get("latency_ms") / count) if count else 0})
            errors = [json.loads(value) for value in values[-1]]
        except Exception:
            checks["Redis"] = {"ok": False, "detail": "Metrics unavailable"}
            traffic, errors = [], []

    activity = {key: "—" for key in ("users", "new_users", "messages", "private_chats", "groups")}
    if checks["Database"]["ok"]:
        try:
            cutoff = now - timedelta(hours=24)
            activity = {"users": User.objects.count(),
                        "new_users": User.objects.filter(date_joined__gte=cutoff).count(),
                        "messages": Message.objects.filter(timestamp__gte=cutoff).count(),
                        "private_chats": PrivateChat.objects.count(),
                        "groups": GroupChat.objects.count()}
        except Exception:
            checks["Database"] = {"ok": False, "detail": "Query failed"}

    return {"checks": checks, "traffic": traffic, "errors": errors, "activity": activity,
            "total_requests": sum(hour["requests"] for hour in traffic),
            "total_failures": sum(hour["failures"] for hour in traffic), "generated_at": now}


@never_cache
@require_GET
def monitor(request):
    if not request.user.is_authenticated or not request.user.is_active or not request.user.is_superuser:
        return HttpResponseForbidden("Superuser access required.")
    return render(request, "chat/monitor.html", operational_snapshot())
