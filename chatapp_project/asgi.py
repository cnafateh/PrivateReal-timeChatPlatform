import os
from django.core.asgi import get_asgi_application

# ابتدا تنظیمات جنگو را load کنید
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatapp_project.settings')

# برنامه Django را قبل از هر چیزی بسازید
django_asgi_app = get_asgi_application()

# حالا ایمپورت‌هایی که به مدل‌های جنگو نیاز دارند
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from chat.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': AuthMiddlewareStack(
        URLRouter(
            websocket_urlpatterns
        )
    ),
})