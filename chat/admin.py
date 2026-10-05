from django.contrib import admin
from django.db.models import Count, Q
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.urls import path, reverse
from django.utils.html import format_html

from .models import Message, PrivateChat, Profile
from .views import attachment_response

admin.site.site_header = "Pulse administration"
admin.site.site_title = "Pulse Admin"
admin.site.index_title = "Administration"
admin.site.site_url = "/"


class ParticipantFilter(admin.SimpleListFilter):
    title = "Participant username"
    parameter_name = "participant"
    template = "admin/participant_filter.html"

    def lookups(self, request, model_admin):
        return ()

    def has_output(self):
        return True

    def choices(self, changelist):
        yield {
            "value": self.value() or "",
            "reset_url": changelist.get_query_string(remove=[self.parameter_name]),
            "preserved": [(key, value) for key, values in changelist.params.items()
                          if key not in {self.parameter_name, "p"} for value in values],
        }

    def queryset(self, request, queryset):
        value = (self.value() or "").strip()
        if not value:
            return queryset
        fields = ("sender", "receiver") if queryset.model is Message else ("user1", "user2")
        return queryset.filter(Q(**{f"{fields[0]}__username__iexact": value}) |
                               Q(**{f"{fields[1]}__username__iexact": value}))


class AttachmentFilter(admin.SimpleListFilter):
    title = "Attachment"
    parameter_name = "has_attachment"

    def lookups(self, request, model_admin):
        return [("yes", "With attachment"), ("no", "Without attachment")]

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.exclude(attachment="")
        if self.value() == "no":
            return queryset.filter(attachment="")
        return queryset


@admin.register(PrivateChat)
class PrivateChatAdmin(admin.ModelAdmin):
    list_display = ["id", "user1", "user2", "message_count", "unread_count", "created_at"]
    list_filter = [ParticipantFilter, "created_at"]
    search_fields = ["user1__username", "user2__username"]
    list_select_related = ["user1", "user2"]
    readonly_fields = ["public_id", "user1", "user2", "created_at", "conversation_messages"]
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

    @admin.display(description="Messages")
    def conversation_messages(self, obj):
        url = reverse("admin:chat_message_changelist")
        return format_html('<a href="{}?chat__id__exact={}">View messages</a>', url, obj.pk)

    def has_add_permission(self, request):
        return False


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ["id", "sender", "receiver", "kind", "short_preview", "file_size", "timestamp", "is_read", "attachment_link"]
    list_filter = [ParticipantFilter, "kind", AttachmentFilter, "is_read", "timestamp",
                   ("sender", admin.RelatedOnlyFieldListFilter), ("receiver", admin.RelatedOnlyFieldListFilter)]
    search_fields = ["sender__username", "receiver__username", "content", "original_name"]
    list_select_related = ["sender", "receiver", "chat"]
    readonly_fields = ["chat", "sender", "receiver", "content", "kind", "original_name",
                       "file_size", "mime_type", "timestamp", "client_id", "is_read", "public_id", "attachment_preview"]
    fields = readonly_fields
    date_hierarchy = "timestamp"
    list_per_page = 50

    @admin.display(description="Preview")
    def short_preview(self, obj):
        return obj.preview[:80]

    def has_add_permission(self, request):
        return False

    def get_urls(self):
        return [path("<uuid:public_id>/attachment/", self.admin_site.admin_view(self.download_attachment),
                     name="chat_message_attachment")] + super().get_urls()

    def download_attachment(self, request, public_id):
        message = get_object_or_404(self.get_queryset(request), public_id=public_id)
        if not self.has_view_or_change_permission(request, message):
            raise PermissionDenied
        return attachment_response(message, request.GET.get("download") == "1")

    @admin.display(description="File")
    def attachment_link(self, obj):
        if not obj.attachment:
            return "—"
        url = reverse("admin:chat_message_attachment", args=[obj.public_id])
        return format_html('<a href="{}?download=1">Download {}</a>', url, obj.original_name)

    @admin.display(description="Attachment")
    def attachment_preview(self, obj):
        if not obj.attachment:
            return "—"
        url = reverse("admin:chat_message_attachment", args=[obj.public_id])
        link = self.attachment_link(obj)
        if obj.kind == Message.Kind.IMAGE:
            return format_html('{}<br><img src="{}" alt="{}" class="admin-attachment-image">', link, url, obj.original_name)
        if obj.kind == Message.Kind.VOICE:
            return format_html('{}<br><audio controls preload="metadata" src="{}"></audio>', link, url)
        return link


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "display_name", "phone", "show_phone", "use_gravatar"]
    list_filter = ["show_phone", "use_gravatar", "user__is_active"]
    search_fields = ["user__username", "user__first_name", "user__last_name", "user__email", "phone"]
    readonly_fields = ["user", "public_id", "display_name"]
    fields = ["user", "public_id", "display_name", "phone", "show_phone", "use_gravatar"]
    list_select_related = ["user"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
