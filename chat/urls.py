from django.urls import path
from . import views

urlpatterns = [
    path("", views.inbox, name="inbox"),
    path("login/", views.login_view, name="login"),
    path("register/", views.register_view, name="register"),
    path("logout/", views.logout_view, name="logout"),
    path("search/", views.search_user, name="search_user"),
    path("chat/<uuid:user_id>/", views.private_chat, name="private_chat"),
    path("groups/<uuid:group_id>/", views.group_chat, name="group_chat"),
    path("api/chat/<uuid:user_id>/", views.get_or_create_chat_api, name="get_or_create_chat_api"),
    path("api/chats/<uuid:chat_id>/messages/", views.message_history, name="message_history"),
    path("api/chats/<uuid:chat_id>/send/", views.send_message, name="send_message"),
    path("api/chats/<uuid:chat_id>/read/", views.mark_read, name="mark_read"),
    path("api/groups/<uuid:group_id>/messages/", views.group_message_history, name="group_message_history"),
    path("api/groups/<uuid:group_id>/send/", views.group_send_message, name="group_send_message"),
    path("api/groups/<uuid:group_id>/read/", views.group_mark_read, name="group_mark_read"),
    path("api/mobile/unread/", views.mobile_unread, name="mobile_unread"),
    path("api/inbox/", views.inbox_updates, name="inbox_updates"),
    path("api/presence/<uuid:public_id>/", views.presence, name="presence"),
    path("api/presence/heartbeat/", views.presence_heartbeat, name="presence_heartbeat"),
    path("profile/edit/", views.edit_profile, name="edit_profile"),
    path("people/<uuid:public_id>/", views.profile_detail, name="profile_detail"),
    path("people/<uuid:public_id>/avatar/", views.profile_avatar, name="profile_avatar"),
    path("attachments/<uuid:message_id>/", views.attachment, name="attachment"),
]
