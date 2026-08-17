from pathlib import Path
import os

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file when it exists.
# In Docker the same variables are injected by docker compose.
load_dotenv(BASE_DIR / ".env", override=False)


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def env_list(name: str, default: str = "") -> list[str]:
    return [
        item.strip()
        for item in os.getenv(name, default).split(",")
        if item.strip()
    ]


# ---------------------------------------------------------
# Core
# ---------------------------------------------------------

SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "django-insecure-development-only-key",
)

DEBUG = env_bool("DEBUG", True)

if not DEBUG and SECRET_KEY == "django-insecure-development-only-key":
    raise RuntimeError(
        "DJANGO_SECRET_KEY must be set when DEBUG=False"
    )


ALLOWED_HOSTS = env_list(
    "ALLOWED_HOSTS",
    "localhost,127.0.0.1",
)

CSRF_TRUSTED_ORIGINS = env_list(
    "CSRF_TRUSTED_ORIGINS"
)


# ---------------------------------------------------------
# Applications
# ---------------------------------------------------------

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "channels",

    "chat",
]


# ---------------------------------------------------------
# Middleware
# ---------------------------------------------------------

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",

    "django.contrib.sessions.middleware.SessionMiddleware",

    "django.middleware.common.CommonMiddleware",

    "django.middleware.csrf.CsrfViewMiddleware",

    "django.contrib.auth.middleware.AuthenticationMiddleware",

    "django.contrib.messages.middleware.MessageMiddleware",

    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


ROOT_URLCONF = "chatapp_project.urls"


# ---------------------------------------------------------
# Templates
# ---------------------------------------------------------

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",

        "DIRS": [
            BASE_DIR / "templates",
        ],

        "APP_DIRS": True,

        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",

                "django.template.context_processors.request",

                "django.contrib.auth.context_processors.auth",

                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


# ---------------------------------------------------------
# WSGI / ASGI
# ---------------------------------------------------------

WSGI_APPLICATION = "chatapp_project.wsgi.application"

ASGI_APPLICATION = "chatapp_project.asgi.application"


# ---------------------------------------------------------
# Database
# ---------------------------------------------------------

# When DB_HOST exists we use PostgreSQL.
# Otherwise SQLite is used for easy local development.

if os.getenv("DB_HOST"):

    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",

            "NAME": os.getenv(
                "DB_NAME",
                "chatapp",
            ),

            "USER": os.getenv(
                "DB_USER",
                "chatapp",
            ),

            "PASSWORD": os.getenv(
                "DB_PASSWORD",
                "chatapp",
            ),

            "HOST": os.getenv(
                "DB_HOST",
                "db",
            ),

            "PORT": os.getenv(
                "DB_PORT",
                "5432",
            ),

            "CONN_MAX_AGE": 60,
        }
    }

else:

    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",

            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


# ---------------------------------------------------------
# Password validation
# ---------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME":
        "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },

    {
        "NAME":
        "django.contrib.auth.password_validation.MinimumLengthValidator"
    },

    {
        "NAME":
        "django.contrib.auth.password_validation.CommonPasswordValidator"
    },

    {
        "NAME":
        "django.contrib.auth.password_validation.NumericPasswordValidator"
    },
]


# ---------------------------------------------------------
# Internationalization
# ---------------------------------------------------------

LANGUAGE_CODE = "en-us"

TIME_ZONE = os.getenv(
    "TIME_ZONE",
    "Asia/Tehran",
)

USE_I18N = True

USE_TZ = True


# ---------------------------------------------------------
# Static files
# ---------------------------------------------------------

STATIC_URL = "/static/"

STATIC_ROOT = BASE_DIR / "staticfiles"


if (BASE_DIR / "static").exists():
    STATICFILES_DIRS = [
        BASE_DIR / "static"
    ]
else:
    STATICFILES_DIRS = []


# ---------------------------------------------------------
# Primary key
# ---------------------------------------------------------

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ---------------------------------------------------------
# Django Channels / Redis
# ---------------------------------------------------------

REDIS_URL = os.getenv("REDIS_URL")


if REDIS_URL:

    CHANNEL_LAYERS = {
        "default": {
            "BACKEND":
            "channels_redis.core.RedisChannelLayer",

            "CONFIG": {
                "hosts": [
                    REDIS_URL
                ],
            },
        },
    }

else:

    # Only suitable for local development.
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND":
            "channels.layers.InMemoryChannelLayer",
        },
    }


# ---------------------------------------------------------
# Authentication
# ---------------------------------------------------------

LOGIN_URL = "login"

LOGIN_REDIRECT_URL = "inbox"

LOGOUT_REDIRECT_URL = "login"


# ---------------------------------------------------------
# Reverse proxy / HTTPS
# ---------------------------------------------------------

SECURE_PROXY_SSL_HEADER = (
    "HTTP_X_FORWARDED_PROTO",
    "https",
)

USE_X_FORWARDED_HOST = True


SECURE_SSL_REDIRECT = env_bool(
    "SECURE_SSL_REDIRECT",
    False,
)


SESSION_COOKIE_SECURE = env_bool(
    "SESSION_COOKIE_SECURE",
    not DEBUG,
)


CSRF_COOKIE_SECURE = env_bool(
    "CSRF_COOKIE_SECURE",
    not DEBUG,
)


SECURE_HSTS_SECONDS = int(
    os.getenv(
        "SECURE_HSTS_SECONDS",
        "0",
    )
)


SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool(
    "SECURE_HSTS_INCLUDE_SUBDOMAINS",
    False,
)


SECURE_HSTS_PRELOAD = env_bool(
    "SECURE_HSTS_PRELOAD",
    False,
)


X_FRAME_OPTIONS = "DENY"

SECURE_CONTENT_TYPE_NOSNIFF = True