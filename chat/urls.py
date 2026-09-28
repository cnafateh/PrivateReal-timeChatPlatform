from django.urls import path
from . import views

urlpatterns = [
    path("", views.inbox, name="inbox"),
    path("login/", views.login_view, name="login"),
    path("register/", views.register_view, name="register"),
    path("logout/", views.logout_view, name="logout"),
    path("search/", views.search_user, name="search_user"),
    path("chat/<int:user_id>/", views.private_chat, name="private_chat"),
    path("api/chat/<int:user_id>/", views.get_or_create_chat_api, name="get_or_create_chat_api"),
    path("api/chats/<int:chat_id>/messages/", views.message_history, name="message_history"),
    path("api/chats/<int:chat_id>/send/", views.send_message, name="send_message"),
    path("api/chats/<int:chat_id>/read/", views.mark_read, name="mark_read"),
    path("attachments/<int:message_id>/", views.attachment, name="attachment"),
]
