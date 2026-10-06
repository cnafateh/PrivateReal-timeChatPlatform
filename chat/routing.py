from django.urls import path

from .consumers import InboxConsumer, PrivateChatConsumer

websocket_urlpatterns = [
    path("ws/inbox/", InboxConsumer.as_asgi()),
    path("ws/chat/private/<uuid:chat_id>/", PrivateChatConsumer.as_asgi()),
]
