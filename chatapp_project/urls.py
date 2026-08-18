from django.contrib import admin
from django.urls import include, path
from chat.views import custom_404

urlpatterns = [
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