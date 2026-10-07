import logging
from pathlib import PurePosixPath

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.urls import reverse
from django.utils import timezone

logger = logging.getLogger(__name__)
MAX_FILE_SIZE = 5 * 1024 * 1024
MAX_MESSAGE_LENGTH = 4000


def serialize_message(message):
    stamp = timezone.localtime(message.timestamp)
    reply = message.reply_to
    return {
        "id": message.pk, "message": message.content,
        "sender": message.sender.username, "sender_id": str(message.sender.profile.public_id),
        "timestamp": stamp.isoformat(), "is_read": message.is_read,
        "kind": message.kind, "name": message.original_name,
        "size": message.file_size, "client_id": str(message.client_id) if message.client_id else None,
        "attachment_url": reverse("attachment", args=[message.public_id]) if message.attachment else None,
        "reply_to": {
            "id": reply.pk,
            "sender": reply.sender.username,
            "message": reply.content[:160],
            "kind": reply.kind,
            "name": reply.original_name,
        } if reply else None,
    }


def broadcast(chat_id, data):
    try:
        async_to_sync(get_channel_layer().group_send)(
            f"private_chat_{chat_id}", {"type": "chat_event", "data": data}
        )
    except Exception:
        # Persistence succeeded; clients recover missed events from message history.
        logger.exception("Could not broadcast conversation %s", chat_id)


def broadcast_group(group_id, data):
    try:
        async_to_sync(get_channel_layer().group_send)(
            f"group_chat_{group_id}", {"type": "chat_event", "data": data}
        )
    except Exception:
        logger.exception("Could not broadcast group %s", group_id)


def broadcast_inbox(message):
    try:
        layer = get_channel_layer()
        user_ids = (message.group.members.values_list("id", flat=True)
                    if message.group_id else (message.sender_id, message.receiver_id))
        for user_id in user_ids:
            async_to_sync(layer.group_send)(
                f"inbox_user_{user_id}", {"type": "inbox_event", "data": {"type": "inbox_update"}}
            )
    except Exception:
        logger.exception("Could not broadcast inbox update for message %s", message.pk)


def inspect_upload(upload, requested_kind):
    from PIL import Image, UnidentifiedImageError
    import warnings

    if not 0 < upload.size <= MAX_FILE_SIZE:
        raise ValueError("Files must be non-empty and no larger than 5 MB.")
    name = PurePosixPath(upload.name.replace("\\", "/")).name[:255]
    kind, mime = "file", "application/octet-stream"
    if requested_kind == "voice":
        header = upload.read(32)
        upload.seek(0)
        if header.startswith(b"\x1aE\xdf\xa3"):
            mime = "audio/webm"
        elif header.startswith(b"OggS"):
            mime = "audio/ogg"
        elif header[4:8] == b"ftyp":
            mime = "audio/mp4"
        elif header.startswith(b"RIFF") and header[8:12] == b"WAVE":
            mime = "audio/wav"
        else:
            raise ValueError("Unsupported voice recording. Use WebM, Ogg, MP4 or WAV.")
        kind = "voice"
    else:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(upload) as image:
                    image.verify()
                    if image.format in {"PNG", "JPEG", "GIF", "WEBP"}:
                        mime = Image.MIME[image.format]
                        kind = "image"
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
            if requested_kind == "image":
                raise ValueError("This image is invalid or too large to display safely.")
        finally:
            upload.seek(0)
    return {"kind": kind, "mime_type": mime, "original_name": name, "file_size": upload.size}
