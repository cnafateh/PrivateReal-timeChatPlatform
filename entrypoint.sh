#!/bin/sh

set -e


echo "Applying database migrations..."

python manage.py migrate --noinput


echo "Collecting static files..."

python manage.py collectstatic \
    --noinput \
    --clear


if [ -n "${DJANGO_SUPERUSER_USERNAME:-}" ] \
    && [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then

    echo "Ensuring admin user exists..."

    python manage.py shell <<'PY'

import os

from django.contrib.auth import get_user_model


User = get_user_model()


username = os.environ[
    "DJANGO_SUPERUSER_USERNAME"
]

email = os.environ.get(
    "DJANGO_SUPERUSER_EMAIL",
    "",
)

password = os.environ[
    "DJANGO_SUPERUSER_PASSWORD"
]


if not User.objects.filter(
    username=username
).exists():

    User.objects.create_superuser(
        username=username,
        email=email,
        password=password,
    )

PY

fi


echo "Starting Daphne..."


exec daphne \
    -b 0.0.0.0 \
    -p 8000 \
    chatapp_project.asgi:application