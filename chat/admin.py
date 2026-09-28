from django.contrib import admin
from django.db.models import Count, Q

from .models import Message, PrivateChat

admin.site.site_header = "Pulse administration"
admin.site.site_title = "Pulse Admin"
admin.site.index_title = "Conversations & community"
admin.site.site_url = "/"


@admin.register(PrivateChat)
class PrivateChatAdmin(admin.ModelAdmin):
    list_display = ["id", "user1", "user2", "message_count", "unread_count", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["user1__username", "user2__username"]
    list_select_related = ["user1", "user2"]
    readonly_fields = ["user1", "user2", "created_at"]
    date_hierarchy = "created_at"
    list_per_page = 50

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            total=Count("messages"), unread=Count("messages", filter=Q(messages__is_read=False)))

    @admin.display(description="Messages", ordering="total")
    def message_count(self, obj):
        return obj.total

    @admin.display(description="Unread", ordering="unread")
    def unread_count(self, obj):
        return obj.unread

    def has_add_permission(self, request):
        return False


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ["id", "sender", "receiver", "kind", "short_preview", "file_size", "timestamp", "is_read"]
    list_filter = ["kind", "is_read", "timestamp"]
    search_fields = ["sender__username", "receiver__username", "content", "original_name"]
    list_select_related = ["sender", "receiver", "chat"]
    readonly_fields = ["chat", "sender", "receiver", "content", "kind", "original_name",
                       "file_size", "mime_type", "timestamp", "client_id", "is_read"]
    fields = readonly_fields
    date_hierarchy = "timestamp"
    list_per_page = 50

    @admin.display(description="Preview")
    def short_preview(self, obj):
        return obj.preview[:80]

    def has_add_permission(self, request):
        return False
