from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.db.models import Count, Q
from django.db import transaction
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.urls import path, reverse
from django.utils.html import format_html

from .forms import clean_avatar_upload
from .models import GroupChat, GroupMembership, Message, PrivateChat, Profile
from .views import attachment_response

admin.site.site_header = "Pulse administration"
admin.site.site_title = "Pulse Admin"
admin.site.index_title = "Administration"
admin.site.site_url = "/"


class ProfileAdminForm(forms.ModelForm):
    new_avatar = forms.FileField(
        required=False,
        label="New profile photo",
        help_text="PNG, JPEG, WebP or GIF, up to 5 MB.",
        widget=forms.FileInput(attrs={"accept": "image/png,image/jpeg,image/webp,image/gif"}),
    )
    remove_avatar = forms.BooleanField(required=False, label="Remove uploaded photo")

    class Meta:
        model = Profile
        fields = ("phone", "show_phone", "use_gravatar")

    def clean_new_avatar(self):
        return clean_avatar_upload(self.cleaned_data["new_avatar"])

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("new_avatar") and cleaned.get("remove_avatar"):
            self.add_error("remove_avatar", "Choose either a new photo or removal, not both.")
        return cleaned


admin.site.unregister(User)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (*BaseUserAdmin.list_display, "chat_profile")
    fieldsets = (*BaseUserAdmin.fieldsets, ("Chat profile", {"fields": ("chat_profile",)}))
    readonly_fields = (*BaseUserAdmin.readonly_fields, "chat_profile")

    @admin.display(description="Chat profile")
    def chat_profile(self, obj):
        if not obj.pk:
            return "Save the user first to edit the profile photo."
        profile = Profile.objects.filter(user=obj).first()
        if not profile:
            return "No profile found."
        url = reverse("admin:chat_profile_change", args=[profile.pk])
        return format_html('<a href="{}">Edit photo and profile settings</a>', url)


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
        if queryset.model is Message:
            return queryset.filter(Q(sender__username__iexact=value) |
                                   Q(receiver__username__iexact=value) |
                                   Q(group__members__username__iexact=value)).distinct()
        return queryset.filter(Q(user1__username__iexact=value) | Q(user2__username__iexact=value))


class GroupMembershipInline(admin.TabularInline):
    model = GroupMembership
    extra = 1
    autocomplete_fields = ["user"]
    readonly_fields = ["joined_at", "last_read_id"]


@admin.register(GroupChat)
class GroupChatAdmin(admin.ModelAdmin):
    list_display = ["name", "member_count", "message_count", "created_by", "created_at"]
    search_fields = ["name", "description", "members__username"]
    list_filter = ["created_at"]
    readonly_fields = ["public_id", "created_by", "created_at"]
    inlines = [GroupMembershipInline]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(total_members=Count("members", distinct=True),
                                                       total_messages=Count("messages", distinct=True))

    @admin.display(description="Members", ordering="total_members")
    def member_count(self, obj):
        return obj.total_members

    @admin.display(description="Messages", ordering="total_messages")
    def message_count(self, obj):
        return obj.total_messages

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


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
    list_display = ["id", "sender", "receiver", "group", "kind", "short_preview", "file_size", "timestamp", "is_read", "attachment_link"]
    list_filter = [ParticipantFilter, "kind", AttachmentFilter, "is_read", "timestamp",
                   ("sender", admin.RelatedOnlyFieldListFilter), ("receiver", admin.RelatedOnlyFieldListFilter)]
    search_fields = ["sender__username", "receiver__username", "group__name", "content", "original_name"]
    list_select_related = ["sender", "receiver", "chat", "group"]
    readonly_fields = ["chat", "group", "sender", "receiver", "reply_to", "content", "kind", "original_name",
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
    form = ProfileAdminForm
    list_display = ["user", "display_name", "phone", "show_phone", "use_gravatar"]
    list_filter = ["show_phone", "use_gravatar", "user__is_active"]
    search_fields = ["user__username", "user__first_name", "user__last_name", "user__email", "phone"]
    readonly_fields = ["user", "public_id", "display_name", "account_links", "avatar_preview"]
    fields = ["user", "public_id", "display_name", "account_links", "avatar_preview",
              "new_avatar", "remove_avatar", "phone", "show_phone", "use_gravatar"]
    list_select_related = ["user"]

    @admin.display(description="User account")
    def account_links(self, obj):
        change_url = reverse("admin:auth_user_change", args=[obj.user_id])
        delete_url = reverse("admin:auth_user_delete", args=[obj.user_id])
        return format_html('<a href="{}">Edit name, email and account</a> · '
                           '<a href="{}">Delete user and profile</a>', change_url, delete_url)

    @admin.display(description="Current photo")
    def avatar_preview(self, obj):
        if not obj.avatar:
            return "No uploaded photo. Gravatar is used when enabled and available."
        url = reverse("admin:chat_profile_avatar", args=[obj.public_id])
        return format_html('<img src="{}" alt="Profile photo" class="admin-profile-image">', url)

    def get_urls(self):
        return [path("<uuid:public_id>/avatar/", self.admin_site.admin_view(self.admin_avatar),
                     name="chat_profile_avatar")] + super().get_urls()

    def admin_avatar(self, request, public_id):
        profile = get_object_or_404(self.get_queryset(request), public_id=public_id)
        if not self.has_view_or_change_permission(request, profile):
            raise PermissionDenied
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

    def save_model(self, request, obj, form, change):
        previous = Profile.objects.filter(pk=obj.pk).values_list("avatar", flat=True).first() or ""
        replacement = form.cleaned_data["new_avatar"]
        new_name = None
        try:
            if replacement:
                obj.avatar.save("avatar.png", replacement, save=False)
                new_name = obj.avatar.name
            elif form.cleaned_data["remove_avatar"]:
                obj.avatar = ""
            super().save_model(request, obj, form, change)
        except Exception:
            if new_name:
                obj.avatar.storage.delete(new_name)
            raise
        if previous and previous != obj.avatar.name:
            storage = obj.avatar.storage
            transaction.on_commit(lambda: storage.delete(previous))

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
