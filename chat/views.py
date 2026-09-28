import uuid

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.db.models import Count, Max, OuterRef, Q, Subquery
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from .forms import RegisterForm
from .models import Message, PrivateChat
from .services import MAX_MESSAGE_LENGTH, broadcast, inspect_upload, serialize_message


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
                 .select_related("user1", "user2")
                 .annotate(last_id=Subquery(latest.values("id")[:1]),
                           unread_count=Count("messages", filter=Q(messages__receiver=user, messages__is_read=False)),
                           activity=Max("messages__timestamp"))
                 .order_by("-activity", "-created_at"))
    last_messages = Message.objects.select_related("sender").in_bulk([c.last_id for c in chats if c.last_id])
    return [{"chat": c, "other_user": c.get_other_user(user),
             "last_message": last_messages.get(c.last_id), "unread_count": c.unread_count} for c in chats]


@login_required
def inbox(request):
    return render(request, "chat/inbox.html", {"chats": conversations(request.user)})


@login_required
def search_user(request):
    query = request.GET.get("q", "").strip()[:150]
    users = list(User.objects.filter(username__iexact=query, is_active=True).exclude(pk=request.user.pk)) if query else []
    message = "No other active user found with that username." if query and not users else None
    return render(request, "chat/search_user.html", {"users": users, "query": query, "message": message})


@login_required
def private_chat(request, user_id):
    other_user = get_object_or_404(User, pk=user_id, is_active=True)
    if other_user == request.user:
        return redirect("inbox")
    chat = PrivateChat.get_or_create_chat(request.user, other_user)
    recent = list(chat.messages.select_related("sender").order_by("-id")[:51])
    initial = [serialize_message(m) for m in reversed(recent[:50])]
    return render(request, "chat/private_chat.html", {
        "chat": chat, "other_user": other_user, "chats": conversations(request.user),
        "chat_config": {"chatId": chat.pk, "userId": request.user.pk,
                        "historyUrl": f"/api/chats/{chat.pk}/messages/",
                        "sendUrl": f"/api/chats/{chat.pk}/send/",
                        "readUrl": f"/api/chats/{chat.pk}/read/",
                        "initial": initial, "hasMore": len(recent) > 50},
    })


@login_required
@require_POST
def get_or_create_chat_api(request, user_id):
    other = get_object_or_404(User, pk=user_id, is_active=True)
    if other == request.user:
        return JsonResponse({"success": False, "error": "You cannot chat with yourself."}, status=400)
    return JsonResponse({"success": True, "chat_id": PrivateChat.get_or_create_chat(request.user, other).pk})


def member_chat(request, chat_id):
    return get_object_or_404(PrivateChat.objects.select_related("user1", "user2")
                            .filter(Q(user1=request.user) | Q(user2=request.user)), pk=chat_id)


@login_required
@require_GET
def message_history(request, chat_id):
    chat = member_chat(request, chat_id)
    query = chat.messages.select_related("sender")
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
    existing = Message.objects.filter(sender=request.user, client_id=client_id).select_related("sender").first()
    if existing:
        if existing.chat_id != chat.pk:
            return JsonResponse({"error": "Message identifier already used."}, status=409)
        return JsonResponse(serialize_message(existing))
    if len(content) > MAX_MESSAGE_LENGTH or not (content or upload):
        return JsonResponse({"error": "Send text or a file; text is limited to 4000 characters."}, status=400)
    metadata = {}
    if upload:
        try:
            metadata = inspect_upload(upload, request.POST.get("kind", "file"))
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
    message = Message(chat=chat, sender=request.user, receiver=chat.get_other_user(request.user),
                      content=content, client_id=client_id, **metadata)
    try:
        with transaction.atomic():
            if upload:
                message.attachment.save(upload.name, upload, save=False)
            message.save()
    except Exception as exc:
        if message.attachment:
            message.attachment.delete(save=False)
        if isinstance(exc, IntegrityError):
            existing = Message.objects.filter(sender=request.user, client_id=client_id, chat=chat).select_related("sender").first()
            if existing:
                return JsonResponse(serialize_message(existing))
        raise
    data = serialize_message(message)
    broadcast(chat.pk, {"type": "message", **data})
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
        broadcast(chat.pk, {"type": "read", "reader_id": request.user.pk, "through": through})
    return JsonResponse({"updated": changed})


@login_required
@require_GET
def attachment(request, message_id):
    message = get_object_or_404(Message.objects.filter(Q(chat__user1=request.user) | Q(chat__user2=request.user)),
                                pk=message_id)
    if not message.attachment:
        raise Http404
    try:
        stream = message.attachment.open("rb")
    except FileNotFoundError:
        raise Http404
    response = FileResponse(stream, content_type=message.mime_type or "application/octet-stream",
                            as_attachment=message.kind == "file" or request.GET.get("download") == "1",
                            filename=message.original_name)
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "default-src 'none'; sandbox"
    return response


def custom_404(request, exception):
    return render(request, "404.html", status=404)
