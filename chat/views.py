import uuid

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.db.models import Count, Max, OuterRef, Q, Subquery
from django.http import FileResponse, Http404, JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_GET, require_POST

from .forms import ProfileForm, RegisterForm
from .models import Message, PrivateChat, Profile
from .services import MAX_MESSAGE_LENGTH, broadcast, broadcast_inbox, inspect_upload, serialize_message


def login_view(request):
    if request.user.is_authenticated:
        return redirect("inbox")
    if request.method == "POST":
        user = authenticate(request, username=request.POST.get("username", "").strip(),
                            password=request.POST.get("password", ""))
        if user:
            login(request, user)
            return redirect("inbox")
        messages.error(request, "Invalid username or password.")
    return render(request, "chat/login.html")


def register_view(request):
    if request.user.is_authenticated:
        return redirect("inbox")
    form = RegisterForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        login(request, form.save())
        return redirect("inbox")
    return render(request, "chat/register.html", {"form": form})


@require_POST
def logout_view(request):
    logout(request)
    return redirect("login")


def conversations(user):
    latest = Message.objects.filter(chat=OuterRef("pk")).order_by("-id")
    chats = list(PrivateChat.objects.filter(Q(user1=user) | Q(user2=user))
                 .select_related("user1__profile", "user2__profile")
                 .annotate(last_id=Subquery(latest.values("id")[:1]),
                           unread_count=Count("messages", filter=Q(messages__receiver=user, messages__is_read=False)),
                           activity=Max("messages__timestamp"))
                 .order_by("-activity", "-created_at"))
    last_messages = Message.objects.select_related("sender__profile").in_bulk([c.last_id for c in chats if c.last_id])
    return [{"chat": c, "other_user": c.get_other_user(user),
             "last_message": last_messages.get(c.last_id), "unread_count": c.unread_count} for c in chats]


@login_required
def inbox(request):
    return render(request, "chat/inbox.html", {"chats": conversations(request.user)})


@login_required
@require_GET
def inbox_updates(request):
    html = render_to_string("chat/conversation_list.html", {"chats": conversations(request.user)}, request)
    return JsonResponse({"html": html})


@login_required
def search_user(request):
    query = request.GET.get("q", "").strip()[:150]
    users = list(User.objects.select_related("profile").filter(username__iexact=query, is_active=True).exclude(pk=request.user.pk)) if query else []
    message = "No other active user found with that username." if query and not users else None
    return render(request, "chat/search_user.html", {"users": users, "query": query, "message": message, "chats": conversations(request.user)})


@login_required
def private_chat(request, user_id):
    other_user = get_object_or_404(User.objects.select_related("profile"), profile__public_id=user_id, is_active=True)
    if other_user == request.user:
        return redirect("inbox")
    chat = PrivateChat.get_or_create_chat(request.user, other_user)
    recent = list(chat.messages.select_related("sender__profile", "reply_to__sender").order_by("-id")[:51])
    initial = [serialize_message(m) for m in reversed(recent[:50])]
    return render(request, "chat/private_chat.html", {
        "chat": chat, "other_user": other_user, "chats": conversations(request.user),
        "chat_config": {"chatId": str(chat.public_id), "userId": str(request.user.profile.public_id),
                        "historyUrl": reverse("message_history", args=[chat.public_id]),
                        "sendUrl": reverse("send_message", args=[chat.public_id]),
                        "readUrl": reverse("mark_read", args=[chat.public_id]),
                        "presenceUrl": reverse("presence", args=[other_user.profile.public_id]),
                        "initial": initial, "hasMore": len(recent) > 50},
    })


@login_required
@require_POST
def get_or_create_chat_api(request, user_id):
    other = get_object_or_404(User.objects.select_related("profile"), profile__public_id=user_id, is_active=True)
    if other == request.user:
        return JsonResponse({"success": False, "error": "You cannot chat with yourself."}, status=400)
    return JsonResponse({"success": True, "chat_id": str(PrivateChat.get_or_create_chat(request.user, other).public_id)})


def member_chat(request, chat_id):
    return get_object_or_404(PrivateChat.objects.select_related("user1__profile", "user2__profile")
                            .filter(Q(user1=request.user) | Q(user2=request.user)), public_id=chat_id)


@login_required
@require_GET
def message_history(request, chat_id):
    chat = member_chat(request, chat_id)
    query = chat.messages.select_related("sender__profile", "reply_to__sender")
    try:
        before = int(request.GET.get("before", 0))
        after = int(request.GET.get("after", 0))
        if before < 0 or after < 0 or (before and after):
            raise ValueError
    except ValueError:
        return JsonResponse({"error": "Invalid message cursor."}, status=400)
    if before:
        query = query.filter(pk__lt=before)
    if after:
        query = query.filter(pk__gt=after)
    rows = list(query.order_by("id" if after else "-id")[:51])
    page = rows[:50] if after else list(reversed(rows[:50]))
    return JsonResponse({"messages": [serialize_message(m) for m in page], "has_more": len(rows) > 50})


@login_required
@require_POST
def send_message(request, chat_id):
    chat = member_chat(request, chat_id)
    content = request.POST.get("message", "").strip()
    upload = request.FILES.get("file")
    if getattr(request, "upload_too_large", False):
        return JsonResponse({"error": "Files may not exceed 5 MB."}, status=400)
    try:
        client_id = uuid.UUID(request.POST.get("client_id", ""))
    except (ValueError, TypeError, AttributeError):
        return JsonResponse({"error": "A valid client_id is required."}, status=400)
    existing = Message.objects.filter(sender=request.user, client_id=client_id).select_related(
        "sender__profile", "reply_to__sender").first()
    if existing:
        if existing.chat_id != chat.pk:
            return JsonResponse({"error": "Message identifier already used."}, status=409)
        return JsonResponse(serialize_message(existing))
    reply_to = None
    if request.POST.get("reply_to"):
        try:
            reply_id = int(request.POST["reply_to"])
        except (ValueError, TypeError):
            return JsonResponse({"error": "Invalid reply target."}, status=400)
        reply_to = chat.messages.select_related("sender").filter(pk=reply_id).first()
        if reply_to is None:
            return JsonResponse({"error": "Invalid reply target."}, status=400)
    if len(content) > MAX_MESSAGE_LENGTH or not (content or upload):
        return JsonResponse({"error": "Send text or a file; text is limited to 4000 characters."}, status=400)
    metadata = {}
    if upload:
        try:
            metadata = inspect_upload(upload, request.POST.get("kind", "file"))
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
    message = Message(chat=chat, sender=request.user, receiver=chat.get_other_user(request.user),
                      content=content, client_id=client_id, reply_to=reply_to, **metadata)
    try:
        with transaction.atomic():
            if upload:
                message.attachment.save(upload.name, upload, save=False)
            message.save()
    except Exception as exc:
        if message.attachment:
            message.attachment.delete(save=False)
        if isinstance(exc, IntegrityError):
            existing = Message.objects.filter(sender=request.user, client_id=client_id, chat=chat).select_related(
                "sender__profile", "reply_to__sender").first()
            if existing:
                return JsonResponse(serialize_message(existing))
        raise
    data = serialize_message(message)
    broadcast(chat.pk, {"type": "message", **data})
    broadcast_inbox(message)
    return JsonResponse(data, status=201)


@login_required
@require_POST
def mark_read(request, chat_id):
    chat = member_chat(request, chat_id)
    try:
        through = int(request.POST.get("through", ""))
        if through < 1:
            raise ValueError
    except ValueError:
        return JsonResponse({"error": "Invalid read cursor."}, status=400)
    changed = chat.messages.filter(receiver=request.user, is_read=False, pk__lte=through).update(is_read=True)
    if changed:
        broadcast(chat.pk, {"type": "read", "reader_id": str(request.user.profile.public_id), "through": through})
        broadcast_inbox(chat.messages.filter(receiver=request.user, pk__lte=through).latest("pk"))
    return JsonResponse({"updated": changed})


@login_required
@require_GET
def mobile_unread(request):
    received = list(Message.objects.filter(receiver=request.user)
                  .select_related("sender__profile", "reply_to__sender", "chat")
                  .order_by("-id")[:50])
    return JsonResponse({"messages": [
        {**serialize_message(message), "chat_id": str(message.chat.public_id),
         "sender_profile_id": str(message.sender.profile.public_id)}
        for message in reversed(received)
    ], "user_id": str(request.user.profile.public_id)})


@login_required
@require_GET
def presence(request, public_id):
    profile = get_object_or_404(Profile, public_id=public_id, user__is_active=True)
    response = JsonResponse({"online": profile.is_online,
                             "last_seen": profile.last_seen.isoformat() if profile.last_seen else None})
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
@require_POST
def presence_heartbeat(request):
    Profile.objects.filter(user=request.user).update(last_seen=timezone.now())
    response = JsonResponse({"ok": True})
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
@require_GET
def attachment(request, message_id):
    message = get_object_or_404(Message.objects.filter(Q(chat__user1=request.user) | Q(chat__user2=request.user)),
                                public_id=message_id)
    return attachment_response(message, request.GET.get("download") == "1")


def attachment_response(message, download=False):
    if not message.attachment:
        raise Http404
    try:
        stream = message.attachment.open("rb")
    except FileNotFoundError:
        raise Http404
    response = FileResponse(stream, content_type=message.mime_type or "application/octet-stream",
                            as_attachment=message.kind == "file" or download,
                            filename=message.original_name)
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "default-src 'none'; sandbox"
    return response


def custom_404(request, exception):
    return render(request, "404.html", status=404)


@login_required
@require_GET
def profile_detail(request, public_id):
    profile = get_object_or_404(Profile.objects.select_related("user"), public_id=public_id, user__is_active=True)
    return render(request, "chat/profile.html", {"profile": profile, "chats": conversations(request.user)})


@login_required
def edit_profile(request):
    profile = request.user.profile
    form = ProfileForm(request.POST if request.method == "POST" else None,
                       request.FILES if request.method == "POST" else None, profile=profile)
    if request.method == "POST" and getattr(request, "upload_too_large", False):
        form.is_valid()
        form.add_error("avatar", "Photos may not exceed 5 MB.")
    elif request.method == "POST" and form.is_valid():
        previous = profile.avatar.name
        replacement = form.cleaned_data["avatar"]
        new_name = None
        try:
            with transaction.atomic():
                user = request.user
                for field in ("first_name", "last_name", "email"):
                    setattr(user, field, form.cleaned_data[field])
                user.save(update_fields=["first_name", "last_name", "email"])
                for field in ("phone", "show_phone", "use_gravatar"):
                    setattr(profile, field, form.cleaned_data[field])
                if replacement:
                    profile.avatar.save("avatar.png", replacement, save=False)
                    new_name = profile.avatar.name
                elif form.cleaned_data["remove_avatar"]:
                    profile.avatar = ""
                profile.save()
                if previous and previous != profile.avatar.name:
                    storage = profile.avatar.storage
                    transaction.on_commit(lambda: storage.delete(previous))
        except Exception:
            if new_name:
                profile.avatar.storage.delete(new_name)
            raise
        return redirect("profile_detail", public_id=profile.public_id)
    return render(request, "chat/edit_profile.html", {"form": form, "profile": profile, "chats": conversations(request.user)})


@login_required
@require_GET
def profile_avatar(request, public_id):
    profile = get_object_or_404(Profile, public_id=public_id, user__is_active=True)
    if not profile.avatar:
        raise Http404
    try:
        stream = profile.avatar.open("rb")
    except FileNotFoundError:
        raise Http404
    response = FileResponse(stream, content_type="image/png")
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
