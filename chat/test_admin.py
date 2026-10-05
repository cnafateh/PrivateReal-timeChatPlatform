import io
import tempfile
from django.contrib.auth.models import Permission, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image
from .models import Message, PrivateChat


class AdminMediaTests(TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        setting = override_settings(MEDIA_ROOT=directory.name)
        setting.enable()
        self.addCleanup(setting.disable)
        self.admin = User.objects.create_superuser("admin", password="test")
        self.alice = User.objects.create_user("alice")
        self.bob = User.objects.create_user("bob")
        self.chat = PrivateChat.get_or_create_chat(self.alice, self.bob)
        data = io.BytesIO()
        Image.new("RGB", (8, 8)).save(data, "PNG")
        self.message = Message.objects.create(chat=self.chat, sender=self.alice, receiver=self.bob,
            kind="image", mime_type="image/png", original_name="photo.png",
            attachment=SimpleUploadedFile("photo.png", data.getvalue()))
        self.url = reverse("admin:chat_message_attachment", args=[self.message.public_id])

    def test_admin_can_preview_and_download_without_chat_membership(self):
        self.client.force_login(self.admin)
        page = self.client.get(reverse("admin:chat_message_change", args=[self.message.pk]))
        self.assertContains(page, self.url)
        self.assertContains(page, "admin-attachment-image")
        for url in [self.url, self.url + "?download=1"]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Content-Type"], "image/png")
            list(response.streaming_content)
        self.assertEqual(self.client.get(reverse("attachment", args=[self.message.public_id])).status_code, 404)

    def test_staff_without_message_permission_cannot_download(self):
        staff = User.objects.create_user("staff", is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        staff.user_permissions.add(Permission.objects.get(codename="view_message"))
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        list(response.streaming_content)
        self.client.force_login(self.alice)
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_filter_matches_sender_or_recipient_and_combines_with_kind(self):
        third = User.objects.create_user("third")
        other_chat = PrivateChat.get_or_create_chat(self.bob, third)
        unrelated = Message.objects.create(chat=other_chat, sender=self.bob, receiver=third, content="unrelated")
        reply = Message.objects.create(chat=self.chat, sender=self.bob, receiver=self.alice, content="reply")
        self.client.force_login(self.admin)
        url = reverse("admin:chat_message_changelist")
        response = self.client.get(url, {"participant":"ALICE"})
        self.assertEqual(set(response.context["cl"].queryset.values_list("pk", flat=True)), {self.message.pk, reply.pk})
        response = self.client.get(url, {"participant":"alice", "kind__exact":"image", "has_attachment":"yes"})
        self.assertEqual(list(response.context["cl"].queryset), [self.message])
        self.assertContains(response, 'name="kind__exact" value="image"')
        response = self.client.get(reverse("admin:chat_privatechat_changelist"), {"participant":"alice"})
        self.assertEqual(list(response.context["cl"].queryset), [self.chat])

    def test_profile_admin_is_searchable_but_cannot_delete_profile(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin:chat_profile_changelist"), {"q":"alice"})
        self.assertEqual(list(response.context["cl"].queryset), [self.alice.profile])
        self.assertEqual(self.client.post(reverse("admin:chat_profile_delete", args=[self.alice.profile.pk]), {"post":"yes"}).status_code, 403)
