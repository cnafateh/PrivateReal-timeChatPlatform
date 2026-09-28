import uuid

from django.contrib.auth.models import User
from django.db import models
from django.db.models import F, Q


def attachment_path(instance, filename):
    return f"attachments/{instance.chat_id}/{uuid.uuid4().hex}"


class PrivateChat(models.Model):
    user1 = models.ForeignKey(User, on_delete=models.CASCADE, related_name="chat_user1")
    user2 = models.ForeignKey(User, on_delete=models.CASCADE, related_name="chat_user2")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user1", "user2")]
        constraints = [models.CheckConstraint(condition=Q(user1__lt=F("user2")), name="chat_ordered_members")]

    def __str__(self):
        return f"{self.user1.username} ↔ {self.user2.username}"

    @staticmethod
    def get_or_create_chat(user_a, user_b):
        if user_a.pk == user_b.pk:
            return None
        first, second = sorted((user_a.pk, user_b.pk))
        return PrivateChat.objects.get_or_create(user1_id=first, user2_id=second)[0]

    def get_other_user(self, current_user):
        if current_user.pk not in (self.user1_id, self.user2_id):
            raise ValueError("User is not a conversation member.")
        return self.user2 if self.user1_id == current_user.pk else self.user1


class Message(models.Model):
    class Kind(models.TextChoices):
        TEXT = "text", "Text"
        IMAGE = "image", "Photo"
        FILE = "file", "File"
        VOICE = "voice", "Voice message"

    chat = models.ForeignKey(PrivateChat, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_messages")
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name="received_messages")
    content = models.TextField(blank=True, max_length=4000)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.TEXT)
    attachment = models.FileField(upload_to=attachment_path, blank=True)
    original_name = models.CharField(max_length=255, blank=True)
    mime_type = models.CharField(max_length=100, blank=True)
    file_size = models.PositiveIntegerField(default=0)
    client_id = models.UUIDField(null=True, blank=True)
    is_read = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["timestamp", "id"]
        indexes = [models.Index(fields=["chat", "id"], name="message_chat_cursor"),
                   models.Index(fields=["receiver", "is_read"], name="message_unread")]
        constraints = [models.UniqueConstraint(fields=["sender", "client_id"], name="message_client_once")]

    @property
    def preview(self):
        return self.content or self.original_name or self.get_kind_display()

    def __str__(self):
        return f"{self.sender.username} → {self.receiver.username}: {self.preview[:60]}"
