from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('chat.urls')),
]

# سرویس فایل‌های استاتیک در حالت DEBUG
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    
    # همچنین برای فایل‌های استاتیک اپلیکیشن‌ها
    urlpatterns += static('/static/', document_root=settings.STATIC_ROOT)