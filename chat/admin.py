from django.contrib import admin
from .models import PrivateChat, Message

@admin.register(PrivateChat)
class PrivateChatAdmin(admin.ModelAdmin):
    list_display = ['id', 'user1', 'user2', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user1__username', 'user2__username']

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['id', 'sender', 'receiver', 'content', 'timestamp', 'is_read']
    list_filter = ['timestamp', 'is_read']
    search_fields = ['sender__username', 'receiver__username', 'content']