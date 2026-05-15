"""Django admin configuration for djgent models."""

import json

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied

from .models import Conversation, HumanInteractionRequest, Message

REVIEWER_PERMISSION = "djgent.can_review_human_interaction"


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
        """Display message count for fieldset."""
        return obj.messages.count()
    message_count_display.short_description = 'Message Count'


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """Admin interface for Message model."""

    list_display = ['truncated_content', 'role', 'conversation', 'tool_name', 'created_at']
    list_filter = ['role', 'created_at', 'conversation__agent_name']
    search_fields = ['content', 'tool_name', 'conversation__name']
    readonly_fields = ['id', 'created_at']
    date_hierarchy = 'created_at'

    def truncated_content(self, obj):
        """Display truncated content."""
        content = obj.content or ''
        return content[:100] + '...' if len(content) > 100 else content
    truncated_content.short_description = 'Content'


def _user_can_review(user) -> bool:
    """Check if user has reviewer permission (superusers always can)."""
    if user.is_superuser:
        return True
    return user.has_perm(REVIEWER_PERMISSION)


@admin.register(HumanInteractionRequest)
class HumanInteractionRequestAdmin(admin.ModelAdmin):
    """Admin interface for Human Interaction Requests.

    Reviewers decide one request at a time. No bulk actions.
    Reject, edit, and cancel decisions require reviewer notes.
    """

    list_display = [
        'public_reference', 'agent_name', 'source', 'operation_name',
        'status', 'notification_state', 'decision', 'reviewer', 'created_at',
    ]
    list_filter = ['status', 'source', 'decision', 'emailed_at', 'created_at']
    search_fields = ['public_reference', 'agent_name', 'thread_id', 'operation_name']
    readonly_fields = [
        'id',
        'public_reference',
        'source',
        'operation_name',
        'operation_type',
        'review_context_display',
        'review_instructions',
        'review_permission',
        'action_requests_display',
        'review_configs_display',
        'site_owner_emails_display',
        'emailed_at',
        'notification_error',
        'created_at',
        'updated_at',
        'decided_at',
        'expires_at',
    ]
    date_hierarchy = 'created_at'
    actions = None  # Disable bulk actions - decisions made one at a time

    fieldsets = (
        ('Request Details', {
            'fields': (
                'id', 'public_reference', 'agent_name', 'thread_id',
                'source', 'operation_name', 'operation_type', 'status',
            )
        }),
        ('Review Context', {
            'fields': (
                'review_context_display', 'review_instructions', 'review_permission',
            )
        }),
        ('Actions', {
            'fields': ('action_requests_display', 'review_configs_display'),
            'classes': ('collapse',)
        }),
        ('Notification', {
            'fields': ('site_owner_emails_display', 'emailed_at', 'notification_error')
        }),
        ('Expiration', {
            'fields': ('expires_at',)
        }),
        ('Review Decision', {
            'fields': (
                'reviewer', 'decision', 'reviewer_notes', 'notes_visible_to_user',
                'decided_at',
            ),
        }),
        ('Resume Metadata', {
            'fields': ('resume_metadata',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def has_view_permission(self, request, obj=None):
        """Enforce reviewer permission for viewing."""
        return _user_can_review(request.user)

    def has_change_permission(self, request, obj=None):
        """Enforce reviewer permission for changing (deciding)."""
        return _user_can_review(request.user)

    def has_add_permission(self, request):
        """Prevent manual creation of human interaction requests."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of human interaction requests."""
        return False

    def notification_state(self, obj):
        """Display notification state."""
        if obj.emailed_at:
            return f"Sent ({obj.emailed_at:%Y-%m-%d %H:%M})"
        if obj.notification_error:
            return f"Failed: {obj.notification_error[:50]}"
        return "Pending"
    notification_state.short_description = 'Notification'

    def review_context_display(self, obj):
        """Display review context as formatted JSON."""
        if not obj.review_context:
            return '-'
        return json.dumps(obj.review_context, indent=2)
    review_context_display.short_description = 'Review Context (safe for reviewers)'

    def action_requests_display(self, obj):
        """Display action requests in a readable format."""
        if not obj.action_requests:
            return '-'
        return json.dumps(obj.action_requests, indent=2)
    action_requests_display.short_description = 'Action Requests (JSON)'

    def review_configs_display(self, obj):
        """Display review configs in a readable format."""
        if not obj.review_configs:
            return '-'
        return json.dumps(obj.review_configs, indent=2)
    review_configs_display.short_description = 'Review Configurations (JSON)'

    def site_owner_emails_display(self, obj):
        """Display site owner emails."""
        if not obj.site_owner_emails:
            return '-'
        return ', '.join(obj.site_owner_emails)
    site_owner_emails_display.short_description = 'Notification Recipients'

    def save_model(self, request, obj, form, change):
        """Apply decision with permission and notes validation."""
        if not change:
            super().save_model(request, obj, form, change)
            return

        # Re-check reviewer permission on decision
        if not _user_can_review(request.user):
            raise PermissionDenied("You do not have permission to review requests.")

        decision = form.cleaned_data.get("decision")
        reviewer_notes = (form.cleaned_data.get("reviewer_notes") or "").strip()

        # Validate notes requirement for reject/edit/cancel
        if decision in (
            HumanInteractionRequest.DECISION_REJECT,
            HumanInteractionRequest.DECISION_EDIT,
            HumanInteractionRequest.DECISION_CANCEL,
        ) and not reviewer_notes:
            messages.error(
                request,
                f"Reviewer notes are required for '{decision}' decisions.",
            )
            return

        # Set reviewer if not already set
        if obj.reviewer is None:
            obj.reviewer = request.user

        # Mark as decidable status
        if obj.is_decidable() and decision:
            obj.status = HumanInteractionRequest.STATUS_RESUMING

        super().save_model(request, obj, form, change)
