import io
import tempfile
import uuid

from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import GroupChat, GroupMembership, Message
from .consumers import GroupChatConsumer


class GroupConversationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser("admin", "admin@example.com", "password")
        cls.alice = User.objects.create_user("alice", password="password")
        cls.bob = User.objects.create_user("bob", password="password")
        cls.outsider = User.objects.create_user("outsider", password="password")
        cls.group = GroupChat.objects.create(name="Project room", created_by=cls.admin)
        GroupMembership.objects.create(group=cls.group, user=cls.alice)
        GroupMembership.objects.create(group=cls.group, user=cls.bob)

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        setting = override_settings(MEDIA_ROOT=directory.name)
        setting.enable()
        self.addCleanup(setting.disable)
        self.client.force_login(self.alice)

    def send(self, **fields):
        fields.setdefault("client_id", str(uuid.uuid4()))
        return self.client.post(reverse("group_send_message", args=[self.group.public_id]), fields)

    def test_admin_creates_group_and_manages_members(self):
        self.client.force_login(self.admin)
        add = reverse("admin:chat_groupchat_add")
        response = self.client.post(add, {
            "name": "New room", "description": "For the team",
            "memberships-TOTAL_FORMS": "1", "memberships-INITIAL_FORMS": "0",
            "memberships-MIN_NUM_FORMS": "0", "memberships-MAX_NUM_FORMS": "1000",
            "memberships-0-user": str(self.alice.pk), "_save": "Save",
        })
        self.assertEqual(response.status_code, 302)
        room = GroupChat.objects.get(name="New room")
        self.assertEqual(room.created_by, self.admin)
        self.assertEqual(list(room.members.all()), [self.alice])

    def test_members_only_can_read_send_and_download(self):
        self.assertContains(self.client.get(reverse("inbox")), "Project room")
        self.assertEqual(self.client.get(reverse("group_chat", args=[self.group.public_id])).status_code, 200)
        sent = self.send(message="Team update")
        self.assertEqual(sent.status_code, 201)
        message = Message.objects.get(pk=sent.json()["id"])
        self.assertEqual(message.group, self.group)
        self.assertIsNone(message.chat)
        self.assertIsNone(message.receiver)
        self.client.force_login(self.outsider)
        self.assertNotContains(self.client.get(reverse("inbox")), "Project room")
        for name in ("group_chat", "group_message_history", "group_send_message", "group_mark_read"):
            url = reverse(name, args=[self.group.public_id])
            response = self.client.post(url, {"message": "Hello"}) if name in ("group_send_message", "group_mark_read") else self.client.get(url)
            self.assertEqual(response.status_code, 404)

    def test_reply_cursor_and_per_member_read_state(self):
        first = self.send(message="First").json()["id"]
        response = self.send(message="Answer", reply_to=first)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["reply_to"]["id"], first)
        self.assertEqual(self.client.get(reverse("group_message_history", args=[self.group.public_id]),
                                         {"after": first}).json()["messages"][0]["id"], response.json()["id"])
        self.assertEqual(self.send(message="Wrong", reply_to=999999).status_code, 400)
        self.client.force_login(self.bob)
        self.assertContains(self.client.get(reverse("inbox")), "2 unread messages")
        read = self.client.post(reverse("group_mark_read", args=[self.group.public_id]), {"through": first})
        self.assertEqual(read.json()["updated"], 1)
        self.assertContains(self.client.get(reverse("inbox")), "1 unread message")
        self.assertEqual(self.client.get(reverse("mobile_unread")).json()["messages"][-1]["destination"],
                         reverse("group_chat", args=[self.group.public_id]))

    def test_idempotence_and_cross_group_reply_rejected(self):
        client_id = str(uuid.uuid4())
        first = self.send(message="Once", client_id=client_id)
        self.assertEqual(first.json()["id"], self.send(message="Once", client_id=client_id).json()["id"])
        other = GroupChat.objects.create(name="Other", created_by=self.admin)
        GroupMembership.objects.create(group=other, user=self.alice)
        self.assertEqual(self.client.post(reverse("group_send_message", args=[other.public_id]),
                                          {"message": "Again", "client_id": client_id}).status_code, 409)
        self.assertEqual(self.client.post(reverse("group_send_message", args=[other.public_id]),
                                          {"message": "Reply", "client_id": str(uuid.uuid4()),
                                           "reply_to": first.json()["id"]}).status_code, 400)

    def test_new_member_starts_read_cursor_at_latest_message(self):
        previous = self.send(message="Before joining").json()["id"]
        membership = GroupMembership.objects.create(group=self.group, user=self.outsider)
        self.assertEqual(membership.last_read_id, previous)
        self.client.force_login(self.outsider)
        self.assertContains(self.client.get(reverse("group_chat", args=[self.group.public_id])), "Before joining")
        self.assertNotContains(self.client.get(reverse("inbox")), "1 unread message")
        self.assertEqual(self.client.get(reverse("mobile_unread")).json()["messages"], [])

    def test_group_image_is_limited_and_private(self):
        photo = io.BytesIO()
        Image.new("RGB", (16, 16), "blue").save(photo, "PNG")
        sent = self.send(file=SimpleUploadedFile("photo.png", photo.getvalue(), "image/png"), kind="image")
        self.assertEqual(sent.status_code, 201)
        message = Message.objects.get(pk=sent.json()["id"])
        url = reverse("attachment", args=[message.public_id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response.close()
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_nonstaff_cannot_create_group_in_admin(self):
        self.assertEqual(self.client.get(reverse("admin:chat_groupchat_add")).status_code, 302)
        self.assertFalse(GroupChat.objects.filter(name="Unauthorized").exists())


class GroupSocketTests(TransactionTestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice")
        self.bob = User.objects.create_user("bob")
        self.group = GroupChat.objects.create(name="Team")
        GroupMembership.objects.create(group=self.group, user=self.alice)

    def socket(self, user):
        socket = WebsocketCommunicator(GroupChatConsumer.as_asgi(), "/ws/")
        socket.scope["user"] = user
        socket.scope["url_route"] = {"kwargs": {"chat_id": str(self.group.public_id)}}
        return socket

    def test_member_typing_and_removed_member_revocation(self):
        async def run():
            outsider = self.socket(self.bob)
            connected, code = await outsider.connect()
            self.assertFalse(connected)
            self.assertEqual(code, 4403)
            await outsider.disconnect()
            member = self.socket(self.alice)
            self.assertTrue((await member.connect())[0])
            try:
                await member.send_json_to({"type": "typing"})
                self.assertEqual((await member.receive_json_from())["type"], "typing")
                await database_sync_to_async(GroupMembership.objects.filter(
                    group=self.group, user=self.alice).delete)()
                await get_channel_layer().group_send(f"group_chat_{self.group.pk}", {
                    "type": "chat_event", "data": {"type": "message", "message": "Hidden"}})
                self.assertEqual((await member.receive_output())["code"], 4403)
            finally:
                await member.disconnect()
        async_to_sync(run)()
