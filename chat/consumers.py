import json
import time

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.db.models import Q

from .models import Message, PrivateChat
from .services import broadcast_inbox, serialize_message


class InboxConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user_id = await self.active_user_id()
        if user_id is None:
            await self.close(code=4403)
            return
        self.room_group_name = f"inbox_user_{user_id}"
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def inbox_event(self, event):
        await self.send(text_data=json.dumps(event["data"]))

    @database_sync_to_async
    def active_user_id(self):
        user = self.scope["user"]
        return user.pk if user.is_authenticated and user.is_active else None


class PrivateChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.chat_id = self.scope["url_route"]["kwargs"]["chat_id"]

        self.last_typing = 0
        if not await self.check_user_access():
            await self.close(code=4403)
            return
        self.room_group_name = f"private_chat_{self.chat_pk}"
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
                "type": "chat_event", "data": {"type": "typing", "sender_id": self.public_user_id}})
            return
        content = payload.get("message")
        if not isinstance(content, str) or not 0 < len(content.strip()) <= 4000:
            return
        message = await self.save_message(content.strip(), payload.get("reply_to"))
        if message:
            await self.channel_layer.group_send(self.room_group_name, {
                "type": "chat_event", "data": {"type": "message", **message}})
            await self.notify_inboxes(message["id"])

    async def chat_event(self, event):
        await self.send(text_data=json.dumps(event["data"]))

    @database_sync_to_async
    def check_user_access(self):
        user = self.scope["user"]
        if not user.is_authenticated:
            return False
        chat = PrivateChat.objects.filter(
            Q(user1_id=user.pk, user1__is_active=True) | Q(user2_id=user.pk, user2__is_active=True),
            public_id=self.chat_id).first()
        if not chat:
            return False
        self.chat_pk = chat.pk
        self.public_user_id = str(user.profile.public_id)
        return True

    @database_sync_to_async
    def save_message(self, content, reply_id):
        user = self.scope["user"]
        chat = PrivateChat.objects.select_related("user1__profile", "user2__profile").filter(
            Q(user1_id=user.pk) | Q(user2_id=user.pk), public_id=self.chat_id).first()
        if not chat:
            return None
        reply_to = None
        if reply_id is not None:
            try:
                reply_to = chat.messages.select_related("sender").filter(pk=int(reply_id)).first()
            except (TypeError, ValueError):
                return None
            if reply_to is None:
                return None
        return serialize_message(Message.objects.create(chat=chat, sender=user,
                                 receiver=chat.get_other_user(user), content=content, reply_to=reply_to))

    @database_sync_to_async
    def notify_inboxes(self, message_id):
        broadcast_inbox(Message.objects.get(pk=message_id))
