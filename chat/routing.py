from django.urls import path

from .consumers import PrivateChatConsumer

websocket_urlpatterns = [
    path("ws/chat/private/<uuid:chat_id>/", PrivateChatConsumer.as_asgi()),
]
