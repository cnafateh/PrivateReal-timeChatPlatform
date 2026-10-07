from django.urls import path

from .consumers import GroupChatConsumer, InboxConsumer, PrivateChatConsumer

websocket_urlpatterns = [
    path("ws/inbox/", InboxConsumer.as_asgi()),
    path("ws/chat/private/<uuid:chat_id>/", PrivateChatConsumer.as_asgi()),
    path("ws/chat/group/<uuid:chat_id>/", GroupChatConsumer.as_asgi()),
]
