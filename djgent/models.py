"""Django models for djgent conversation history."""

import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class Conversation(models.Model):
    """
    Represents a conversation session.

    Stores conversation history for agents with persistent memory.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for this conversation"
    )
    name = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Optional name for this conversation"
    )
    agent_name = models.CharField(
        max_length=255,
        help_text="Name of the agent this conversation belongs to"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='djgent_conversations',
        help_text="User associated with this conversation (optional)"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this conversation was created"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When this conversation was last updated"
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata for this conversation"
    )
    input_tokens = models.BigIntegerField(default=0)
    output_tokens = models.BigIntegerField(default=0)
    total_tokens = models.BigIntegerField(default=0)
    estimated_cost = models.DecimalField(
        max_digits=18,
        decimal_places=8,
        default=Decimal("0"),
    )

    class Meta:
        db_table = 'djgent_conversation'
        ordering = ['-updated_at']
        verbose_name = 'Conversation'
        verbose_name_plural = 'Conversations'

    def __str__(self):
        name = self.name or f"Conversation {str(self.id)[:8]}"
        return f"{name} ({self.agent_name})"

    @property
    def message_count(self):
        """Return the number of messages in this conversation."""
        return self.messages.count()

    def get_recent_messages(self, limit: int = None):
        """Get recent messages from this conversation."""
        queryset = self.messages.all()
        if limit:
            queryset = queryset[:limit]
        return list(queryset)

    def to_dict(self):
        """Convert conversation to dictionary."""
        return {
            'id': str(self.id),
            'name': self.name,
            'agent_name': self.agent_name,
            'user_id': self.user_id,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'message_count': self.message_count,
            'input_tokens': self.input_tokens,
            'output_tokens': self.output_tokens,
            'total_tokens': self.total_tokens,
            'estimated_cost': str(self.estimated_cost),
            'metadata': self.metadata,
        }

    def get_runtime_state(self, thread_id: str = "default"):
        """Return persisted runtime state for a thread."""
        runtime_state = self.metadata.get("runtime_state", {})
        return runtime_state.get(thread_id, {})

    def set_runtime_state(self, thread_id: str, state: dict):
        """Persist runtime state for a thread."""
        metadata = dict(self.metadata or {})
        runtime_state = dict(metadata.get("runtime_state", {}))
        runtime_state[thread_id] = state
        metadata["runtime_state"] = runtime_state
        self.metadata = metadata
        self.save(update_fields=["metadata", "updated_at"])

    def touch(self):
        """Refresh the conversation timestamp."""
        self.updated_at = timezone.now()
        self.save(update_fields=["updated_at"])

    def add_usage(
        self,
        *,
        input_tokens: int = 0,
        output_tokens: int = 0,
        total_tokens: int = 0,
        estimated_cost: Decimal | float | str = Decimal("0"),
    ) -> None:
        """Accumulate usage totals for the conversation."""
        self.input_tokens += int(input_tokens or 0)
        self.output_tokens += int(output_tokens or 0)
        self.total_tokens += int(total_tokens or (input_tokens + output_tokens))
        self.estimated_cost += Decimal(str(estimated_cost or "0"))
        self.updated_at = timezone.now()
        self.save(
            update_fields=[
                "input_tokens",
                "output_tokens",
                "total_tokens",
                "estimated_cost",
                "updated_at",
            ]
        )


class Message(models.Model):
    """
    Individual message in a conversation.

    Stores both human and AI messages with role information.
    """

    ROLE_CHOICES = [
        ('human', 'Human'),
        ('ai', 'AI'),
        ('system', 'System'),
    ]

    conversation = models.ForeignKey(
        Conversation,
        related_name='messages',
        on_delete=models.CASCADE,
        help_text="The conversation this message belongs to"
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        help_text="The role of the message sender"
    )
    content = models.TextField(
        help_text="The message content"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this message was created"
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata for this message"
    )
    input_tokens = models.BigIntegerField(default=0)
    output_tokens = models.BigIntegerField(default=0)
    total_tokens = models.BigIntegerField(default=0)
    estimated_cost = models.DecimalField(
        max_digits=18,
        decimal_places=8,
        default=Decimal("0"),
    )

    class Meta:
        db_table = 'djgent_message'
        ordering = ['created_at']
        verbose_name = 'Message'
        verbose_name_plural = 'Messages'
        indexes = [
            models.Index(fields=['conversation', '-created_at']),
            models.Index(fields=['role']),
        ]

    def __str__(self):
        preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"{self.role}: {preview}"

    def to_dict(self):
        """Convert message to dictionary."""
        return {
            'id': self.id,
            'conversation_id': str(self.conversation.id),
            'role': self.role,
            'content': self.content,
            'created_at': self.created_at.isoformat(),
            'input_tokens': self.input_tokens,
            'output_tokens': self.output_tokens,
            'total_tokens': self.total_tokens,
            'estimated_cost': str(self.estimated_cost),
            'metadata': self.metadata,
        }

    def to_langchain_message(self):
        """Convert to LangChain message format."""
        from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

        role_map = {
            'human': HumanMessage,
            'ai': AIMessage,
            'system': SystemMessage,
        }

        message_class = role_map.get(self.role, HumanMessage)
        return message_class(content=self.content)


class MemoryFact(models.Model):
    """
    Long-term memory item associated with a user or conversation.
    """

    scope = models.CharField(max_length=32, default="user")
    key = models.CharField(max_length=255)
    value = models.TextField()
    agent_name = models.CharField(max_length=255, blank=True, default="")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="djgent_memory_facts",
    )
    conversation = models.ForeignKey(
        Conversation,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="memory_facts",
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "djgent_memory_fact"
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["scope", "key"]),
            models.Index(fields=["agent_name"]),
        ]

    def __str__(self):
        return f"{self.scope}:{self.key}"


class KnowledgeDocument(models.Model):
    """
    Simple knowledge-base document for retrieval workflows.
    """

    namespace = models.CharField(max_length=255, default="default")
    title = models.CharField(max_length=255)
    content = models.TextField()
    source = models.CharField(max_length=512, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "djgent_knowledge_document"
        ordering = ["title", "-updated_at"]
        indexes = [
            models.Index(fields=["namespace"]),
            models.Index(fields=["title"]),
        ]

    def __str__(self):
        return f"{self.namespace}:{self.title}"




class AuditLog(models.Model):
    """Model for storing audit logs in the database."""

    event_id = models.CharField(max_length=36, unique=True, db_index=True)
    event_type = models.CharField(max_length=50, db_index=True)
    level = models.CharField(max_length=20)
    agent_name = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    thread_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    user_id = models.IntegerField(blank=True, null=True, db_index=True)
    session_id = models.CharField(max_length=100, blank=True, null=True)
    conversation_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    tool_name = models.CharField(max_length=100, blank=True, null=True)
    details = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True, null=True)
    duration_ms = models.FloatField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(
                fields=['agent_name', 'timestamp'],
                name='djgent_audit_agent_ts_idx',
            ),
            models.Index(
                fields=['user_id', 'timestamp'],
                name='djgent_audit_user_ts_idx',
            ),
            models.Index(
                fields=['conversation_id', 'timestamp'],
                name='djgent_audit_conv_ts_idx',
            ),
        ]

    def __str__(self) -> str:
        return f"{self.event_type} - {self.agent_name} - {self.timestamp}"
