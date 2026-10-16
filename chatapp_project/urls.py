from django.contrib import admin
from django.urls import include, path
from chat.views import custom_404
from chat.monitoring import monitor

urlpatterns = [
    path("monitir/", monitor, name="monitor"),
    path(
        "admin/",
        admin.site.urls,
    ),

    path(
        "",
        include("chat.urls"),
    ),
]


handler404 = "chat.views.custom_404"
