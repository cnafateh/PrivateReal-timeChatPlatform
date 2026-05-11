#!/bin/bash

echo "🚀 Starting Django Chat App..."

# بارگذاری متغیرهای محیطی از فایل .env
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# اجرای مایگریشن‌ها
echo "📦 Running migrations..."
python manage.py makemigrations --noinput
python manage.py migrate --noinput

# ساخت خودکار سوپر یوزر (اگه از قبل نباشه)
echo "👤 Creating superuser (if not exists)..."
python manage.py shell << EOF
from django.contrib.auth import get_user_model;
User = get_user_model();
username = "$DJANGO_SUPERUSER_USERNAME";
email = "$DJANGO_SUPERUSER_EMAIL";
password = "$DJANGO_SUPERUSER_PASSWORD";
if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username, email, password)
    print(f"✅ Superuser '{username}' created successfully!")
else:
    print(f"✅ Superuser '{username}' already exists.")
EOF

echo "✅ Starting Daphne server..."
daphne -b 0.0.0.0 -p 8000 chatapp_project.asgi:application