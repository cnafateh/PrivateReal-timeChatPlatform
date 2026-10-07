import os

os.environ["DB_HOST"] = ""
os.environ["REDIS_URL"] = ""
os.environ["DEBUG"] = "True"

from .settings import *  # noqa: F403

SECRET_KEY = "test-only-secret-key-not-for-deployment"
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
if os.environ.get("TEST_DB_HOST"):
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.postgresql", "NAME": "pulse_test",
        "USER": "postgres", "PASSWORD": "postgres",
        "HOST": os.environ["TEST_DB_HOST"], "PORT": os.environ.get("TEST_DB_PORT", "5432"),
    }}
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
if os.environ.get("TEST_REDIS_URL"):
    CHANNEL_LAYERS = {"default": {"BACKEND": "channels_redis.core.RedisChannelLayer",
                                "CONFIG": {"hosts": [os.environ["TEST_REDIS_URL"]]}}}
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
# Live-server browser requests run in another thread; avoid a second connection to the in-memory session table.
SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
