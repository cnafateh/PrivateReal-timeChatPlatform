import json
import time

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.db.models import Q

from .models import Message, PrivateChat
from .services import serialize_message


class PrivateChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.chat_id = self.scope["url_route"]["kwargs"]["chat_id"]
        self.room_group_name = f"private_chat_{self.chat_id}"
        self.last_typing = 0
        if not await self.check_user_access():
            await self.close(code=4403)
            return
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data or len(text_data) > 20000:
            return
        try:
            payload = json.loads(text_data)
        except (ValueError, TypeError):
            return
        if not isinstance(payload, dict) or not await self.check_user_access():
            return
        if payload.get("type") == "typing":
            if time.monotonic() - self.last_typing < 2:
                return
            self.last_typing = time.monotonic()
            await self.channel_layer.group_send(self.room_group_name, {
                "type": "chat_event", "data": {"type": "typing", "sender_id": self.scope["user"].pk}})
            return
        content = payload.get("message")
        if not isinstance(content, str) or not 0 < len(content.strip()) <= 4000:
            return
        message = await self.save_message(content.strip())
        if message:
            await self.channel_layer.group_send(self.room_group_name, {
                "type": "chat_event", "data": {"type": "message", **message}})

    async def chat_event(self, event):
        await self.send(text_data=json.dumps(event["data"]))

    @database_sync_to_async
    def check_user_access(self):
        user = self.scope["user"]
        return user.is_authenticated and user.is_active and PrivateChat.objects.filter(
            Q(user1_id=user.pk) | Q(user2_id=user.pk), pk=self.chat_id).exists()

    @database_sync_to_async
    def save_message(self, content):
        user = self.scope["user"]
        chat = PrivateChat.objects.select_related("user1", "user2").filter(
            Q(user1_id=user.pk) | Q(user2_id=user.pk), pk=self.chat_id).first()
        if not chat:
            return None
        return serialize_message(Message.objects.create(chat=chat, sender=user,
                                 receiver=chat.get_other_user(user), content=content))
