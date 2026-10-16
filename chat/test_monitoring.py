import tempfile
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from . import monitoring
from .auth_limits import _key, login_is_limited, note_login_failure


class FakePipeline:
    def __init__(self, client):
        self.client = client
        self.commands = []

    def __getattr__(self, command):
        def queue(*args, **kwargs):
            self.commands.append((command, args, kwargs))
            return self
        return queue

    def execute(self):
        results = [getattr(self.client, command)(*args, **kwargs)
                   for command, args, kwargs in self.commands]
        self.commands = []
        return results


class FakeRedis:
    def __init__(self):
        self.hashes, self.lists, self.values = {}, {}, {}

    def ping(self):
        return True

    def pipeline(self, transaction=False):
        return FakePipeline(self)

    def hincrby(self, key, field, amount):
        data = self.hashes.setdefault(key, {})
        data[field.encode()] = data.get(field.encode(), 0) + amount
        return data[field.encode()]

    def hgetall(self, key):
        return self.hashes.get(key, {})

    def lpush(self, key, value):
        self.lists.setdefault(key, []).insert(0, value.encode())

    def ltrim(self, key, start, end):
        self.lists[key] = self.lists[key][start:end + 1]

    def lrange(self, key, start, end):
        return self.lists.get(key, [])[start:end + 1]

    def expire(self, key, seconds, nx=False):
        return True

    def get(self, key):
        return self.values.get(key)

    def incr(self, key):
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]

    def delete(self, key):
        self.values.pop(key, None)


class MonitorTests(TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.override = override_settings(MEDIA_ROOT=self.directory.name, REDIS_URL="redis://monitor-test/0")
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.redis = FakeRedis()
        self.mock = patch("chat.monitoring.redis_client", return_value=self.redis)
        self.mock.start()
        self.addCleanup(self.mock.stop)
        self.auth_mock = patch("chat.auth_limits.redis_client", return_value=self.redis)
        self.auth_mock.start()
        self.addCleanup(self.auth_mock.stop)
        self.admin = User.objects.create_superuser("operator", password="secret")
        self.staff = User.objects.create_user("staff", password="secret", is_staff=True)

    def test_monitor_is_superuser_only_and_uncacheable(self):
        url = reverse("monitor")
        self.assertEqual(url, "/monitor/")
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.admin)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertContains(response, "Media storage")
        self.assertContains(response, "Database")

    def test_metrics_aggregate_without_request_identity(self):
        now = timezone.now()
        monitoring.record_request("send_message", 500, 43, now=now)
        snapshot = monitoring.operational_snapshot(now)
        self.assertEqual(snapshot["total_requests"], 1)
        self.assertEqual(snapshot["total_failures"], 1)
        self.assertEqual(snapshot["traffic"][-1]["average_ms"], 43)
        self.assertEqual(snapshot["errors"][0]["route"], "send_message")
        stored = repr(self.redis.lists)
        self.assertNotIn("operator", stored)
        self.assertNotIn("/api/", stored)
        monitoring.record_request("monitor", 200, 2, now=now)
        self.assertEqual(monitoring.operational_snapshot(now)["total_requests"], 1)

    def test_login_throttle_after_ten_failures(self):
        for _ in range(10):
            note_login_failure("operator")
        self.assertTrue(login_is_limited("operator"))
        self.assertNotIn("operator", _key("operator"))
        response = self.client.post(reverse("login"), {"username": "operator", "password": "secret"})
        self.assertEqual(response.status_code, 429)
        self.assertFalse(response.has_header("Location"))

    def test_monitor_degrades_without_redis(self):
        with patch("chat.monitoring.redis_client", side_effect=OSError("offline")):
            snapshot = monitoring.operational_snapshot()
        self.assertFalse(snapshot["checks"]["Redis"]["ok"])
        self.assertTrue(snapshot["checks"]["Database"]["ok"])
        self.assertEqual(snapshot["traffic"], [])
