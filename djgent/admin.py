"""Django admin configuration for djgent models."""

from django.contrib import admin

from .models import Conversation, HumanInteractionRequest, Message


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    """Admin interface for Conversation model."""

    list_display = ['name_display', 'agent_name', 'user', 'message_count', 'total_tokens', 'estimated_cost', 'created_at', 'updated_at']
    list_filter = ['agent_name', 'created_at', 'user']
    search_fields = ['name', 'messages__content', 'id']
    readonly_fields = [
        'id',
        'created_at',
        'updated_at',
        'message_count_display',
        'input_tokens',
        'output_tokens',
        'total_tokens',
        'estimated_cost',
    ]
    date_hierarchy = 'created_at'

    fieldsets = (
        (None, {
            'fields': ('id', 'name', 'agent_name', 'user')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': (
                'message_count_display',
                'input_tokens',
                'output_tokens',
                'total_tokens',
                'estimated_cost',
            ),
            'classes': ('collapse',)
        }),
    )

    def name_display(self, obj):
        """Display name or truncated ID."""
        return obj.name or f"Conversation {str(obj.id)[:8]}"
    name_display.short_description = 'Name'

    def message_count(self, obj):
        """Return the number of messages."""
        return obj.messages.count()
    message_count.short_description = 'Messages'

    def message_count_display(self, obj):
        """Display message count in fieldset."""
        return obj.messages.count()
    message_count_display.short_description = 'Total Messages'

    def get_queryset(self, request):
        """Optimize queryset with prefetch."""
        return super().get_queryset(request).prefetch_related('messages')


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """Admin interface for Message model."""

    list_display = ['conversation_link', 'role', 'content_preview', 'total_tokens', 'estimated_cost', 'created_at']
    list_filter = ['role', 'created_at', 'conversation__agent_name']
    search_fields = ['content', 'conversation__name', 'conversation__id']
    readonly_fields = [
        'id',
        'created_at',
        'conversation_link',
        'input_tokens',
        'output_tokens',
        'total_tokens',
        'estimated_cost',
    ]
    date_hierarchy = 'created_at'

    fieldsets = (
        (None, {
            'fields': ('conversation', 'role', 'content')
        }),
        ('Metadata', {
            'fields': ('metadata', 'input_tokens', 'output_tokens', 'total_tokens', 'estimated_cost'),
            'classes': ('collapse',)
        }),
        ('Timestamp', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def conversation_link(self, obj):
        """Link to conversation."""
        return obj.conversation
    conversation_link.short_description = 'Conversation'

    def content_preview(self, obj):
        """Preview of message content."""
        content = obj.content
        if len(content) > 50:
            content = content[:50] + "..."
        return content
    content_preview.short_description = 'Content'

    def get_queryset(self, request):
        """Optimize queryset with select related."""
        return super().get_queryset(request).select_related('conversation')


@admin.register(HumanInteractionRequest)
class HumanInteractionRequestAdmin(admin.ModelAdmin):
    """Admin queue for site-owner HITL approvals."""

    list_display = [
        "id",
        "status",
        "agent_name",
        "thread_id",
        "owner_email_preview",
        "created_at",
        "emailed_at",
        "resumed_at",
    ]
    list_filter = ["status", "agent_name", "created_at", "emailed_at"]
    search_fields = ["id", "agent_name", "thread_id", "site_owner_emails"]
    readonly_fields = [
        "id",
        "agent_name",
        "thread_id",
        "conversation",
        "requesting_user",
        "site_owner_emails",
        "action_requests",
        "review_configs",
        "output",
        "error",
        "notification_error",
        "emailed_at",
        "decided_at",
        "resumed_at",
        "created_at",
        "updated_at",
    ]
    actions = ["approve_selected", "reject_selected", "resume_selected"]
    date_hierarchy = "created_at"

    fieldsets = (
        (None, {"fields": ("id", "status", "agent_name", "thread_id")}),
        (
            "Review",
            {
                "fields": (
                    "action_requests",
                    "review_configs",
                    "decisions",
                    "site_owner_emails",
                )
            },
        ),
        (
            "Context",
            {
                "fields": (
                    "conversation",
                    "requesting_user",
                    "output",
                    "error",
                    "notification_error",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "emailed_at",
                    "decided_at",
                    "resumed_at",
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("conversation", "requesting_user")
        )

    def owner_email_preview(self, obj):
        return ", ".join(obj.site_owner_emails or [])[:80]

    owner_email_preview.short_description = "Site owners"

    @admin.action(description="Approve selected HITL requests")
    def approve_selected(self, request, queryset):
        from django.utils import timezone

        count = 0
        for item in queryset.filter(status=HumanInteractionRequest.STATUS_PENDING):
            item.status = HumanInteractionRequest.STATUS_APPROVED
            item.decisions = [
                {"type": "approve"} for _ in (item.action_requests or [])
            ]
            item.decided_at = timezone.now()
            item.save(update_fields=["status", "decisions", "decided_at", "updated_at"])
            count += 1
        self.message_user(request, f"Approved {count} request(s).")

    @admin.action(description="Reject selected HITL requests")
    def reject_selected(self, request, queryset):
        from django.utils import timezone

        count = 0
        for item in queryset.filter(status=HumanInteractionRequest.STATUS_PENDING):
            item.status = HumanInteractionRequest.STATUS_REJECTED
            item.decisions = [
                {"type": "reject", "message": "Rejected by site owner."}
                for _ in (item.action_requests or [])
            ]
            item.decided_at = timezone.now()
            item.save(update_fields=["status", "decisions", "decided_at", "updated_at"])
            count += 1
        self.message_user(request, f"Rejected {count} request(s).")

    @admin.action(description="Resume selected HITL requests")
    def resume_selected(self, request, queryset):
        from djgent import Agent

        resumed = 0
        for item in queryset.filter(
            status__in=[
                HumanInteractionRequest.STATUS_PENDING,
                HumanInteractionRequest.STATUS_APPROVED,
                HumanInteractionRequest.STATUS_REJECTED,
            ]
        ):
            try:
                agent = Agent.create(
                    name=item.agent_name,
                    auto_load_tools=True,
                    memory=True,
                    memory_backend="database",
                    conversation_id=(
                        str(item.conversation_id)
                        if item.conversation_id
                        else None
                    ),
                    thread_id=item.thread_id,
                )
                agent.resume_human_interaction(
                    item.id,
                    decisions=item.decisions or None,
                    reviewer=request.user,
                )
                resumed += 1
            except Exception as exc:
                item.status = HumanInteractionRequest.STATUS_FAILED
                item.error = str(exc)
                item.save(update_fields=["status", "error", "updated_at"])
        self.message_user(request, f"Resumed {resumed} request(s).")
