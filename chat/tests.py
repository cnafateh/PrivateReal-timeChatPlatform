import io
import json
import tempfile
import uuid
from datetime import timedelta
from unittest.mock import patch

from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import AnonymousUser, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from .consumers import PrivateChatConsumer
from .models import Message, PrivateChat
from .services import MAX_FILE_SIZE, serialize_message


class ChatTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = User.objects.create_user("alice", password="correct-password")
        cls.bob = User.objects.create_user("bob", password="correct-password")
        cls.eve = User.objects.create_user("eve", password="correct-password")
        cls.chat = PrivateChat.get_or_create_chat(cls.alice, cls.bob)

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        settings = override_settings(MEDIA_ROOT=directory.name)
        settings.enable()
        self.addCleanup(settings.disable)
        self.client.force_login(self.alice)

    def send(self, **data):
        data.setdefault("client_id", str(uuid.uuid4()))
        return self.client.post(reverse("send_message", args=[self.chat.pk]), data)

    def message(self, **kwargs):
        values = dict(chat=self.chat, sender=self.alice, receiver=self.bob, content="Hello")
        values.update(kwargs)
        return Message.objects.create(**values)

    def test_chat_pair_is_canonical(self):
        self.assertEqual(PrivateChat.get_or_create_chat(self.bob, self.alice), self.chat)
        self.assertIsNone(PrivateChat.get_or_create_chat(self.alice, self.alice))
        self.assertEqual(PrivateChat.objects.count(), 1)
        with self.assertRaises(ValueError):
            self.chat.get_other_user(self.eve)

    def test_database_rejects_reversed_pair(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            PrivateChat.objects.create(user1=self.bob, user2=self.alice)

    def test_authentication_and_registration(self):
        self.client.logout()
        self.assertRedirects(self.client.get("/"), "/login/?next=/")
        self.assertContains(self.client.post("/login/", {"username": "alice", "password": "wrong"}), "Invalid username")
        self.assertRedirects(self.client.post("/login/", {"username": "alice", "password": "correct-password"}), "/")
        self.client.logout()
        response = self.client.post("/register/", {"username":"new-person", "password1":"Long-Unusual-374!", "password2":"Long-Unusual-374!"})
        self.assertRedirects(response, "/")
        self.assertTrue(User.objects.filter(username="new-person").exists())

    def test_logout_requires_post(self):
        self.assertEqual(self.client.get("/logout/").status_code, 405)
        self.assertRedirects(self.client.post("/logout/"), "/login/")

    def test_csrf_is_required(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.alice)
        for name, args in [("send_message", [self.chat.pk]), ("mark_read", [self.chat.pk]), ("logout", [])]:
            self.assertEqual(client.post(reverse(name, args=args), {"message":"hello"}).status_code, 403)

    def test_private_pages_and_theme_controls(self):
        for url in ["/", "/search/", reverse("private_chat", args=[self.bob.pk])]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'id="theme-toggle"')
        self.assertRedirects(self.client.get(reverse("private_chat", args=[self.alice.pk])), "/")

    def test_search_handles_case_variants_without_crashing(self):
        User.objects.create_user("BOB")
        response = self.client.get("/search/", {"q":"bob"})
        self.assertEqual(len(response.context["users"]), 2)

    def test_send_text_has_iso_timestamp_and_identity(self):
        response = self.send(message="  Hello فارسی  ")
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["message"], "Hello فارسی")
        self.assertEqual(data["sender_id"], self.alice.pk)
        self.assertIn("T", data["timestamp"])
        self.assertEqual(Message.objects.get().receiver, self.bob)

    def test_invalid_text_and_client_id(self):
        for data in [{"message":" "}, {"message":"x" * 4001}, {"message":"ok", "client_id":"invalid"}]:
            self.assertEqual(self.send(**data).status_code, 400)
        self.assertEqual(Message.objects.count(), 0)
        self.assertEqual(self.send(message="x" * 4000).status_code, 201)

    def test_idempotent_retry(self):
        client_id = str(uuid.uuid4())
        first = self.send(message="Hello", client_id=client_id)
        retry = self.send(message="Hello", client_id=client_id)
        self.assertEqual(first.json()["id"], retry.json()["id"])
        self.assertEqual(Message.objects.count(), 1)
        other = PrivateChat.get_or_create_chat(self.alice, self.eve)
        response = self.client.post(reverse("send_message", args=[other.pk]), {"message":"other", "client_id":client_id})
        self.assertEqual(response.status_code, 409)

    def test_broadcast_failure_does_not_lose_message(self):
        with patch("chat.services.get_channel_layer", side_effect=RuntimeError("unavailable")), self.assertLogs("chat.services", level="ERROR"):
            response = self.send(message="Still saved")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Message.objects.count(), 1)

    def test_history_and_send_are_member_only(self):
        self.client.force_login(self.eve)
        for name in ["message_history", "send_message", "mark_read"]:
            url = reverse(name, args=[self.chat.pk])
            response = self.client.get(url) if name == "message_history" else self.client.post(url)
            self.assertEqual(response.status_code, 404)
        self.assertEqual(Message.objects.count(), 0)

    def test_attachment_validation_boundaries(self):
        for size in [0, MAX_FILE_SIZE + 1]:
            response = self.send(file=SimpleUploadedFile("document.bin", b"x" * size))
            self.assertEqual(response.status_code, 400)
        response = self.send(file=SimpleUploadedFile("document.bin", b"x" * MAX_FILE_SIZE))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["size"], MAX_FILE_SIZE)

    def test_oversized_upload_does_not_save_caption(self):
        response = self.send(message="Do not save without the file", file=SimpleUploadedFile("huge.bin", b"x" * (MAX_FILE_SIZE + 1)))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Message.objects.count(), 0)
        self.assertEqual(self.send(file=SimpleUploadedFile("huge.bin", b"x" * (7 * 1024 * 1024))).status_code, 413)

    def test_verified_photo_and_caption(self):
        content = io.BytesIO()
        Image.new("RGB", (8, 8), "red").save(content, format="PNG")
        response = self.send(message="Photo", file=SimpleUploadedFile("photo.png", content.getvalue(), "image/png"))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["kind"], "image")
        download = self.client.get(response.json()["attachment_url"])
        self.assertEqual(download["Content-Type"], "image/png")
        self.assertTrue(download["Content-Disposition"].startswith("inline"))
        list(download.streaming_content)

    def test_spoofed_image_is_not_served_inline(self):
        response = self.send(file=SimpleUploadedFile("fake.png", b"<script>alert(1)</script>", "image/png"))
        self.assertEqual(response.json()["kind"], "file")
        download = self.client.get(response.json()["attachment_url"])
        self.assertEqual(download["Content-Type"], "application/octet-stream")
        self.assertTrue(download["Content-Disposition"].startswith("attachment"))
        self.assertEqual(download["X-Content-Type-Options"], "nosniff")
        list(download.streaming_content)
        self.assertEqual(self.send(kind="image", file=SimpleUploadedFile("bad.png", b"bad")).status_code, 400)

    def test_voice_container_validation(self):
        response = self.send(kind="voice", file=SimpleUploadedFile("voice.webm", b"\x1aE\xdf\xa3" + b"x" * 32, "audio/webm"))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["kind"], "voice")
        self.assertEqual(self.send(kind="voice", file=SimpleUploadedFile("voice.webm", b"bad")).status_code, 400)

    def test_attachment_authorization(self):
        response = self.send(file=SimpleUploadedFile("notes.txt", b"private notes"))
        url = response.json()["attachment_url"]
        self.client.force_login(self.bob)
        download = self.client.get(url)
        self.assertEqual(download.status_code, 200)
        self.assertEqual(b"".join(download.streaming_content), b"private notes")
        self.assertEqual(download["Cache-Control"], "private, no-store")
        list(download.streaming_content)
        self.client.force_login(self.eve)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)

    def test_history_pagination_and_catchup(self):
        rows = [self.message(content=str(i)) for i in range(105)]
        url = reverse("message_history", args=[self.chat.pk])
        latest = self.client.get(url).json()
        self.assertTrue(latest["has_more"])
        self.assertEqual([m["id"] for m in latest["messages"]], [m.pk for m in rows[-50:]])
        older = self.client.get(url, {"before":rows[-50].pk}).json()
        self.assertEqual([m["id"] for m in older["messages"]], [m.pk for m in rows[5:55]])
        newer = self.client.get(url, {"after":rows[0].pk}).json()
        self.assertTrue(newer["has_more"])
        self.assertEqual(newer["messages"][0]["id"], rows[1].pk)
        for params in [{"before":"bad"}, {"after":-1}, {"after":1, "before":2}]:
            self.assertEqual(self.client.get(url, params).status_code, 400)

    def test_read_receipts_only_mark_received_through_cursor(self):
        first = self.message(sender=self.bob, receiver=self.alice)
        later = self.message(sender=self.bob, receiver=self.alice)
        own = self.message()
        response = self.client.post(reverse("mark_read", args=[self.chat.pk]), {"through":first.pk})
        self.assertEqual(response.json()["updated"], 1)
        first.refresh_from_db(); later.refresh_from_db(); own.refresh_from_db()
        self.assertTrue(first.is_read)
        self.assertFalse(later.is_read)
        self.assertFalse(own.is_read)
        self.assertEqual(self.client.post(reverse("mark_read", args=[self.chat.pk]), {"through":"bad"}).status_code, 400)

    def test_inbox_has_constant_query_count(self):
        for i in range(8):
            person = User.objects.create_user(f"person{i}")
            chat = PrivateChat.get_or_create_chat(self.alice, person)
            self.message(chat=chat, receiver=person)
        from .views import conversations
        with self.assertNumQueries(2):
            self.assertEqual(len(conversations(self.alice)), 9)

    def test_script_content_is_safe_in_initial_json(self):
        self.message(content='</script><script>alert("x")</script>')
        response = self.client.get(reverse("private_chat", args=[self.bob.pk]))
        self.assertNotContains(response, '</script><script>alert')
        self.assertContains(response, r'\u003C/script\u003E')

    def test_serialized_date_includes_day_and_timezone(self):
        message = self.message()
        date = timezone.now() - timedelta(days=2)
        Message.objects.filter(pk=message.pk).update(timestamp=date)
        message.refresh_from_db()
        self.assertEqual(serialize_message(message)["timestamp"], timezone.localtime(date).isoformat())

    def test_admin_pages(self):
        admin = User.objects.create_superuser("admin", password="password")
        self.client.force_login(admin)
        self.message()
        for url in ["/admin/", "/admin/chat/privatechat/", "/admin/chat/message/", f"/admin/chat/message/{Message.objects.first().pk}/change/"]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Pulse")


class SocketTests(TransactionTestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice")
        self.bob = User.objects.create_user("bob")
        self.eve = User.objects.create_user("eve")
        self.chat = PrivateChat.get_or_create_chat(self.alice, self.bob)

    def socket(self, user):
        communicator = WebsocketCommunicator(PrivateChatConsumer.as_asgi(), "/ws/")
        communicator.scope["user"] = user
        communicator.scope["url_route"] = {"kwargs":{"chat_id":str(self.chat.pk)}}
        return communicator

    def test_rejects_anonymous_and_nonmembers(self):
        async def run():
            for user in [AnonymousUser(), self.eve]:
                socket = self.socket(user)
                connected, code = await socket.connect()
                self.assertFalse(connected)
                self.assertEqual(code, 4403)
                await socket.disconnect()
        async_to_sync(run)()

    def test_broadcast_and_malformed_payload_recovery(self):
        async def run():
            first, second = self.socket(self.alice), self.socket(self.bob)
            self.assertTrue((await first.connect())[0])
            self.assertTrue((await second.connect())[0])
            try:
                for payload in ['[]', 'null', 'broken', '{"message":{}}', '{"message":" "}']:
                    await first.send_to(text_data=payload)
                await first.send_json_to({"message":"Hello"})
                own = await first.receive_json_from()
                other = await second.receive_json_from()
                self.assertEqual(own, other)
                self.assertEqual(other["message"], "Hello")
                self.assertIn("T", other["timestamp"])
                await first.send_json_to({"type":"typing"})
                self.assertEqual((await second.receive_json_from())["type"], "typing")
                self.assertEqual((await first.receive_json_from())["type"], "typing")
            finally:
                await first.disconnect(); await second.disconnect()
        async_to_sync(run)()
        self.assertEqual(Message.objects.count(), 1)

    def test_origin_validator_rejects_foreign_site(self):
        from chatapp_project.asgi import application
        async def run():
            socket = WebsocketCommunicator(application, f"/ws/chat/private/{self.chat.pk}/",
                                            headers=[(b"origin", b"https://untrusted.example")])
            connected, _ = await socket.connect()
            self.assertFalse(connected)
            await socket.disconnect()
        async_to_sync(run)()

    def test_http_send_broadcasts_saved_attachment(self):
        from channels.db import database_sync_to_async
        client = Client()
        client.force_login(self.alice)
        with tempfile.TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            async def run():
                socket = self.socket(self.bob)
                self.assertTrue((await socket.connect())[0])
                try:
                    response = await database_sync_to_async(client.post)(
                        reverse("send_message", args=[self.chat.pk]),
                        {"client_id":str(uuid.uuid4()), "file":SimpleUploadedFile("hello.txt", b"Hello")})
                    self.assertEqual(response.status_code, 201)
                    event = await socket.receive_json_from()
                    self.assertEqual(event["id"], response.json()["id"])
                    self.assertEqual(event["kind"], "file")
                    self.assertEqual(event["name"], "hello.txt")
                finally:
                    await socket.disconnect()
            async_to_sync(run)()
