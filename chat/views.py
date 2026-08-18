from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .forms import RegisterForm
from django.contrib.auth.models import User
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)

from .models import Message, PrivateChat


def login_view(request):

    if request.user.is_authenticated:
        return redirect("inbox")

    if request.method == "POST":

        username = request.POST.get(
            "username",
            "",
        ).strip()

        password = request.POST.get(
            "password",
            "",
        )

        user = authenticate(
            request,
            username=username,
            password=password,
        )

        if user:

            login(
                request,
                user,
            )

            return redirect(
                "inbox"
            )

        messages.error(
    request,
    "Invalid username or password.",
)

    return render(
        request,
        "chat/login.html",
    )


def register_view(request):

    if request.user.is_authenticated:
        return redirect("inbox")

    if request.method == "POST":

        form = RegisterForm(
            request.POST
        )

        if form.is_valid():

            user = form.save()

            login(
                request,
                user,
            )

            return redirect(
                "inbox"
            )

    else:

        form = RegisterForm()

    return render(
        request,
        "chat/register.html",
        {
            "form": form,
        },
    )


def logout_view(request):

    logout(request)

    return redirect(
        "login"
    )


@login_required
def inbox(request):

    chats = (
        PrivateChat.objects
        .filter(
            Q(user1=request.user)
            |
            Q(user2=request.user)
        )
        .select_related(
            "user1",
            "user2",
        )
    )


    chats_data = []


    for chat in chats:

        other_user = chat.get_other_user(
            request.user
        )


        last_message = (
            chat.messages
            .select_related(
                "sender"
            )
            .last()
        )


        unread_count = (
            chat.messages
            .filter(
                receiver=request.user,
                is_read=False,
            )
            .count()
        )


        chats_data.append(
            {
                "chat":
                chat,

                "other_user":
                other_user,

                "last_message":
                last_message,

                "unread_count":
                unread_count,
            }
        )


    chats_data.sort(
        key=lambda item: (
            item["last_message"].timestamp
            if item["last_message"]
            else item["chat"].created_at
        ),
        reverse=True,
    )


    return render(
        request,
        "chat/inbox.html",
        {
            "chats":
            chats_data,
        },
    )


@login_required
def search_user(request):

    query = request.GET.get(
        "q",
        "",
    ).strip()


    users = []

    message = None


    if query:

        try:

            found_user = User.objects.get(
                username__iexact=query
            )


            if found_user == request.user:

                message = "You cannot start a conversation with yourself."

            else:

                users = [
                    found_user
                ]


        except User.DoesNotExist:

            message = f'No user found with the username "{query}".'


    return render(
        request,
        "chat/search_user.html",
        {
            "users":
            users,

            "query":
            query,

            "message":
            message,
        },
    )


@login_required
def private_chat(
    request,
    user_id,
):

    other_user = get_object_or_404(
        User,
        id=user_id,
    )


    if other_user == request.user:

        messages.warning(
            request,
            "You cannot start a conversation with yourself.",
        )

        return redirect(
            "inbox"
        )


    chat = PrivateChat.get_or_create_chat(
        request.user,
        other_user,
    )


    if not chat:

        messages.error(
            request,
            "Unable to create the conversation.",
        )

        return redirect(
            "inbox"
        )


    Message.objects.filter(
        chat=chat,
        receiver=request.user,
        is_read=False,
    ).update(
        is_read=True
    )


    # Get last 100 messages.
    latest_messages = list(
        Message.objects
        .filter(
            chat=chat
        )
        .select_related(
            "sender",
            "receiver",
        )
        .order_by(
            "-timestamp"
        )[:100]
    )


    # Reverse them again so template renders
    # oldest -> newest.
    latest_messages.reverse()


    return render(
        request,
        "chat/private_chat.html",
        {
            "chat":
            chat,

            "other_user":
            other_user,

            "messages":
            latest_messages,
        },
    )


@login_required
def get_or_create_chat_api(
    request,
    user_id,
):

    other_user = get_object_or_404(
        User,
        id=user_id,
    )


    if other_user == request.user:

        return JsonResponse(
            {
                "success":
                False,

                "error":
                "You cannot chat with yourself.",
            },
            status=400,
        )


    chat = PrivateChat.get_or_create_chat(
        request.user,
        other_user,
    )


    if not chat:

        return JsonResponse(
            {
                "success":
                False,
            },
            status=400,
        )


    return JsonResponse(
        {
            "success":
            True,

            "chat_id":
            chat.id,
        }
    )

def custom_404(
    request,
    exception,
):
    return render(
        request,
        "404.html",
        status=404,
    )