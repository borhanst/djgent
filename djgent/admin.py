"""Django admin configuration for djgent models."""

from django.contrib import admin

from .models import Conversation, Message


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    """Admin interface for Conversation model."""

    list_display = [
        "name_display",
        "agent_name",
        "user",
        "message_count",
        "total_tokens",
        "estimated_cost",
        "created_at",
        "updated_at",
    ]
    list_filter = ["agent_name", "created_at", "user"]
    search_fields = ["name", "messages__content", "id"]
    readonly_fields = [
        "id",
        "created_at",
        "updated_at",
        "message_count_display",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "estimated_cost",
    ]
    date_hierarchy = "created_at"

    fieldsets = (
        (None, {"fields": ("id", "name", "agent_name", "user")}),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
        ("Metadata", {"fields": ("metadata",), "classes": ("collapse",)}),
        (
            "Statistics",
            {
                "fields": (
                    "message_count_display",
                    "input_tokens",
                    "output_tokens",
                    "total_tokens",
                    "estimated_cost",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def name_display(self, obj):
        """Display name or truncated ID."""
        return obj.name or f"Conversation {str(obj.id)[:8]}"

    name_display.short_description = "Name"

    def message_count(self, obj):
        """Return the number of messages."""
        return obj.messages.count()

    message_count.short_description = "Messages"

    def message_count_display(self, obj):
        """Display message count in fieldset."""
        return obj.messages.count()

    message_count_display.short_description = "Total Messages"

    def get_queryset(self, request):
        """Optimize queryset with prefetch."""
        return super().get_queryset(request).prefetch_related("messages")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """Admin interface for Message model."""

    list_display = [
        "conversation_link",
        "role",
        "content_preview",
        "total_tokens",
        "estimated_cost",
        "created_at",
    ]
    list_filter = ["role", "created_at", "conversation__agent_name"]
    search_fields = ["content", "conversation__name", "conversation__id"]
    readonly_fields = [
        "id",
        "created_at",
        "conversation_link",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "estimated_cost",
    ]
    date_hierarchy = "created_at"

    fieldsets = (
        (None, {"fields": ("conversation", "role", "content")}),
        (
            "Metadata",
            {
                "fields": (
                    "metadata",
                    "input_tokens",
                    "output_tokens",
                    "total_tokens",
                    "estimated_cost",
                ),
                "classes": ("collapse",),
            },
        ),
        ("Timestamp", {"fields": ("created_at",), "classes": ("collapse",)}),
    )

    def conversation_link(self, obj):
        """Link to conversation."""
        return obj.conversation

    conversation_link.short_description = "Conversation"

    def content_preview(self, obj):
        """Preview of message content."""
        content = obj.content
        if len(content) > 50:
            content = content[:50] + "..."
        return content

    content_preview.short_description = "Content"

    def get_queryset(self, request):
        """Optimize queryset with select related."""
        return super().get_queryset(request).select_related("conversation")
