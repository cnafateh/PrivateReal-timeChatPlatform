import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils import timezone

from .models import Message, PrivateChat


class PrivateChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):

        self.chat_id = self.scope[
            "url_route"
        ]["kwargs"]["chat_id"]

        self.room_group_name = (
            f"private_chat_{self.chat_id}"
        )

        has_access = await self.check_user_access()

        if not has_access:
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name,
        )

        await self.accept()


    async def disconnect(self, close_code):

        if hasattr(
            self,
            "room_group_name",
        ):

            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name,
            )


    async def receive(
        self,
        text_data=None,
        bytes_data=None,
    ):

        try:

            payload = json.loads(
                text_data or "{}"
            )

        except json.JSONDecodeError:
            return


        content = str(
            payload.get(
                "message",
                "",
            )
        ).strip()


        if not content:
            return


        if len(content) > 4000:
            return


        message = await self.save_message(
            content
        )


        if not message:
            return


        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",

                "message":
                message["content"],

                "sender":
                message["sender"],

                "timestamp":
                message["timestamp"],
            },
        )


    async def chat_message(
        self,
        event,
    ):

        await self.send(
            text_data=json.dumps(
                {
                    "message":
                    event["message"],

                    "sender":
                    event["sender"],

                    "timestamp":
                    event["timestamp"],
                }
            )
        )


    @database_sync_to_async
    def check_user_access(self):

        user = self.scope["user"]


        if not user.is_authenticated:
            return False


        return (
            PrivateChat.objects
            .filter(id=self.chat_id)
            .filter(
                user1=user
            )
            .exists()

            or

            PrivateChat.objects
            .filter(id=self.chat_id)
            .filter(
                user2=user
            )
            .exists()
        )


    @database_sync_to_async
    def save_message(
        self,
        content,
    ):

        user = self.scope["user"]


        chat = (
            PrivateChat.objects
            .filter(
                id=self.chat_id
            )
            .select_related(
                "user1",
                "user2",
            )
            .first()
        )


        if not chat:
            return None


        if user not in (
            chat.user1,
            chat.user2,
        ):
            return None


        receiver = (
            chat.user2
            if chat.user1 == user
            else chat.user1
        )


        message = Message.objects.create(
            chat=chat,
            sender=user,
            receiver=receiver,
            content=content,
            is_read=False,
        )


        local_time = timezone.localtime(
            message.timestamp
        )


        return {
            "content":
            message.content,

            "sender":
            user.username,

            "timestamp":
            local_time.strftime("%H:%M"),
        }