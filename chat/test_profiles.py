import hashlib
import io
import tempfile
import uuid

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import Message, PrivateChat, Profile


class ProfileTests(TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        settings = override_settings(MEDIA_ROOT=self.directory.name)
        settings.enable()
        self.addCleanup(settings.disable)
        self.alice = User.objects.create_user("alice", email="Alice@Example.com")
        self.bob = User.objects.create_user("bob")
        self.client.force_login(self.alice)

    def photo(self):
        data = io.BytesIO()
        Image.new("RGB", (800, 600), "red").save(data, "JPEG", comment=b"private metadata")
        return SimpleUploadedFile("photo.jpg", data.getvalue(), "image/jpeg")

    def test_profile_is_created_and_uuid_is_random(self):
        self.assertEqual(Profile.objects.count(), 2)
        self.assertEqual(self.alice.profile.public_id.version, 4)
        self.assertNotEqual(self.alice.profile.public_id, self.bob.profile.public_id)
        self.assertEqual(self.alice.profile.display_name, "alice")

    def test_edit_own_profile_and_keep_contacts_private(self):
        response = self.client.post(reverse("edit_profile"), {
            "first_name":"Alice", "last_name":"Example", "email":"private@example.com",
            "phone":"+۹۸ (۹۱۲) ۱۲۳-۴۵۶۷", "use_gravatar":"on", "user":self.bob.pk})
        self.assertRedirects(response, reverse("profile_detail", args=[self.alice.profile.public_id]))
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.get_full_name(), "Alice Example")
        self.assertEqual(self.alice.profile.phone, "+989121234567")
        self.bob.refresh_from_db()
        self.assertEqual(self.bob.first_name, "")
        self.client.force_login(self.bob)
        response = self.client.get(reverse("profile_detail", args=[self.alice.profile.public_id]))
        self.assertContains(response, "Alice Example")
        self.assertNotContains(response, "private@example.com")
        self.assertNotContains(response, "+989121234567")
        self.alice.profile.show_phone = True
        self.alice.profile.save()
        self.assertContains(self.client.get(reverse("profile_detail", args=[self.alice.profile.public_id])), "+989121234567")

    def test_profile_edit_requires_login_and_csrf(self):
        self.client.logout()
        for url in [reverse("edit_profile"), reverse("profile_detail", args=[self.alice.profile.public_id]), reverse("profile_avatar", args=[self.alice.profile.public_id])]:
            self.assertEqual(self.client.get(url).status_code, 302)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.alice)
        self.assertEqual(client.post(reverse("edit_profile"), {"first_name":"changed"}).status_code, 403)

    def test_invalid_phone_and_image_do_not_save_names(self):
        for data in [{"phone":"09121234567"}, {"avatar":SimpleUploadedFile("bad.png", b"<script>bad</script>")},
                     {"avatar":SimpleUploadedFile("big.png", b"x" * (5 * 1024 * 1024 + 1))}]:
            response = self.client.post(reverse("edit_profile"), {"first_name":"Must not persist", **data})
            self.assertIn(response.status_code, [200, 400])
            self.alice.refresh_from_db()
            self.assertEqual(self.alice.first_name, "")
            self.assertFalse(self.alice.profile.avatar)

    def test_avatar_is_resized_reencoded_and_removable(self):
        response = self.client.post(reverse("edit_profile"), {"avatar":self.photo(), "use_gravatar":"on"})
        self.assertEqual(response.status_code, 302)
        profile = Profile.objects.get(user=self.alice)
        with profile.avatar.open("rb") as stream, Image.open(stream) as image:
            self.assertEqual(image.format, "PNG")
            self.assertEqual(image.size, (512, 384))
            self.assertNotIn("comment", image.info)
        url = reverse("profile_avatar", args=[profile.public_id])
        self.client.force_login(self.bob)
        response = self.client.get(url)
        self.assertEqual(response["Content-Type"], "image/png")
        list(response.streaming_content)
        self.client.force_login(self.alice)
        old_name = profile.avatar.name
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("edit_profile"), {"remove_avatar":"on", "use_gravatar":"on"})
        self.assertFalse(profile.avatar.storage.exists(old_name))
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_gravatar_uses_normalized_sha256_and_can_be_disabled(self):
        profile = self.alice.profile
        digest = hashlib.sha256(b"alice@example.com").hexdigest()
        self.assertEqual(profile.avatar_url, f"https://gravatar.com/avatar/{digest}?s=160&d=404&r=g")
        profile.use_gravatar = False
        self.assertEqual(profile.avatar_url, "")
        self.assertEqual(self.bob.profile.avatar_url, "")

    def test_avatar_upload_and_remove_conflict_is_reported(self):
        response = self.client.post(reverse("edit_profile"), {"avatar":self.photo(), "remove_avatar":"on"})
        self.assertContains(response, "Choose either a new photo or removal")
        self.assertFalse(Profile.objects.get(user=self.alice).avatar)

    def test_public_routes_reject_sequential_ids_and_unknown_uuids(self):
        chat = PrivateChat.get_or_create_chat(self.alice, self.bob)
        message = Message.objects.create(chat=chat, sender=self.alice, receiver=self.bob, content="Private")
        for path in [f"/chat/{self.bob.pk}/", f"/api/chat/{self.bob.pk}/", f"/api/chats/{chat.pk}/messages/", f"/attachments/{message.pk}/", f"/people/{self.bob.pk}/"]:
            self.assertEqual(self.client.get(path).status_code, 404)
        self.assertEqual(self.client.get(reverse("private_chat", args=[uuid.uuid4()])).status_code, 404)
        response = self.client.get(reverse("private_chat", args=[self.bob.profile.public_id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["chat_config"]["chatId"], str(chat.public_id))
        self.assertEqual(response.context["chat_config"]["userId"], str(self.alice.profile.public_id))
        self.assertEqual(response.context["chat_config"]["sendUrl"], reverse("send_message", args=[chat.public_id]))

    def test_inactive_profiles_are_unavailable(self):
        self.bob.is_active = False
        self.bob.save()
        for name in ["profile_detail", "profile_avatar", "private_chat"]:
            self.assertEqual(self.client.get(reverse(name, args=[self.bob.profile.public_id])).status_code, 404)

    def test_owner_profile_has_edit_action(self):
        self.assertContains(self.client.get(reverse("profile_detail", args=[self.alice.profile.public_id])),
                            reverse("edit_profile"))
        self.assertNotContains(self.client.get(reverse("profile_detail", args=[self.bob.profile.public_id])),
                               reverse("edit_profile"))

    def test_chat_creation_api_returns_public_uuid(self):
        response = self.client.post(reverse("get_or_create_chat_api", args=[self.bob.profile.public_id]))
        self.assertEqual(response.status_code, 200)
        chat = PrivateChat.objects.get()
        self.assertEqual(response.json()["chat_id"], str(chat.public_id))

    def test_registration_saves_optional_gravatar_email(self):
        self.client.logout()
        response = self.client.post(reverse("register"), {"username":"new-person", "email":"new@example.com",
            "password1":"Long-374-Unusual!", "password2":"Long-374-Unusual!"})
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username="new-person")
        self.assertEqual(user.email, "new@example.com")
        self.assertIn(hashlib.sha256(b"new@example.com").hexdigest(), user.profile.avatar_url)
