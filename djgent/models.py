"""Django models for djgent conversation history."""

import json
import secrets
import uuid
from datetime import datetime
from decimal import Decimal

from django.conf import settings
from django.core import signing
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


class HumanInteractionRequest(models.Model):
    """First-class review request for protected agent operations."""

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_RESUMING = "resuming"
    STATUS_RESUMED = "resumed"
    STATUS_RESUME_FAILED = "resume_failed"
    STATUS_EXPIRED = "expired"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_RESUMING, "Resuming"),
        (STATUS_RESUMED, "Resumed"),
        (STATUS_RESUME_FAILED, "Resume Failed"),
        (STATUS_EXPIRED, "Expired"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    SOURCE_DJGENT_NATIVE = "djgent_native"
    SOURCE_LANGGRAPH_HITL = "langgraph_hitl"

    SOURCE_CHOICES = [
        (SOURCE_DJGENT_NATIVE, "Djgent Native"),
        (SOURCE_LANGGRAPH_HITL, "LangGraph HITL"),
    ]

    OPERATION_TYPE_TOOL = "tool"
    OPERATION_TYPE_OPERATION = "operation"

    OPERATION_TYPE_CHOICES = [
        (OPERATION_TYPE_TOOL, "Tool"),
        (OPERATION_TYPE_OPERATION, "Operation"),
    ]

    DECISION_APPROVE = "approve"
    DECISION_REJECT = "reject"
    DECISION_EDIT = "edit"
    DECISION_CANCEL = "cancel"

    DECISION_CHOICES = [
        (DECISION_APPROVE, "Approve"),
        (DECISION_REJECT, "Reject"),
        (DECISION_EDIT, "Edit"),
        (DECISION_CANCEL, "Cancel"),
    ]

    DECIDABLE_STATUSES = (STATUS_PENDING, STATUS_APPROVED, STATUS_REJECTED)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    public_reference = models.CharField(
        max_length=32,
        unique=True,
        db_index=True,
        blank=True,
    )
    status = models.CharField(
        max_length=32,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    source = models.CharField(
        max_length=32,
        choices=SOURCE_CHOICES,
        default=SOURCE_DJGENT_NATIVE,
        db_index=True,
    )
    agent_name = models.CharField(max_length=255, db_index=True)
    thread_id = models.CharField(max_length=255, db_index=True)
    conversation = models.ForeignKey(
        Conversation,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="human_interaction_requests",
    )
    requesting_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="djgent_human_interaction_requests",
    )
    operation_name = models.CharField(max_length=255, blank=True, default="")
    operation_type = models.CharField(
        max_length=32,
        choices=OPERATION_TYPE_CHOICES,
        default=OPERATION_TYPE_TOOL,
    )
    review_context = models.JSONField(default=dict, blank=True)
    review_instructions = models.TextField(blank=True, default="")
    review_permission = models.CharField(max_length=255, blank=True, default="")
    expires_at = models.DateTimeField(null=True, blank=True)
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_hitl_requests",
    )
    reviewer_notes = models.TextField(blank=True, default="")
    notes_visible_to_user = models.BooleanField(default=False)
    decision = models.CharField(
        max_length=32,
        choices=DECISION_CHOICES,
        blank=True,
        default="",
    )
    site_owner_emails = models.JSONField(default=list, blank=True)
    action_requests = models.JSONField(default=list, blank=True)
    review_configs = models.JSONField(default=list, blank=True)
    decisions = models.JSONField(default=list, blank=True)
    output = models.TextField(blank=True, default="")
    error = models.TextField(blank=True, default="")
    notification_error = models.TextField(blank=True, default="")
    resume_payload_encrypted = models.BinaryField(null=True, blank=True)
    resume_payload_key_version = models.CharField(
        max_length=32, blank=True, default=""
    )
    emailed_at = models.DateTimeField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    resumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "djgent_human_interaction_request"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["agent_name", "status"]),
            models.Index(fields=["thread_id", "status"]),
            models.Index(fields=["source", "status", "-created_at"]),
        ]

    def __str__(self) -> str:
        ref = self.public_reference or str(self.id)[:8]
        return f"{ref}:{self.status}"

    def save(self, *args, **kwargs):
        if not self.public_reference:
            self.public_reference = self._generate_public_reference()
        super().save(*args, **kwargs)

    @classmethod
    def _generate_public_reference(cls) -> str:
        """Generate a unique public reference like HITL-20260515-A1B2C3D4."""
        date_part = datetime.now().strftime("%Y%m%d")
        while True:
            token = secrets.token_hex(4).upper()
            ref = f"HITL-{date_part}-{token}"
            if not cls.objects.filter(public_reference=ref).exists():
                return ref

    def get_payload_encryption_key(self) -> str:
        """Return the key used for resume payload encryption."""
        from djgent.utils.helpers import get_djent_setting

        key = get_djent_setting("HUMAN_IN_THE_LOOP", {}).get("PAYLOAD_KEY")
        return key or settings.SECRET_KEY

    def set_resume_payload(self, data: dict) -> None:
        """Encrypt and store the resume payload."""
        key = self.get_payload_encryption_key()
        signed = signing.dumps(data, key=key, salt="djgent-hitl-resume")
        self.resume_payload_encrypted = signed.encode("utf-8")
        self.save(update_fields=[
            "resume_payload_encrypted", "resume_payload_key_version", "updated_at"
        ])

    def get_resume_payload(self) -> dict | None:
        """Decrypt and return the resume payload."""
        if not self.resume_payload_encrypted:
            return None
        key = self.get_payload_encryption_key()
        try:
            raw = self.resume_payload_encrypted.decode("utf-8")
            return signing.loads(raw, key=key, salt="djgent-hitl-resume")
        except (signing.BadSignature, signing.SignatureExpired):
            return None

    def clear_resume_payload(self) -> None:
        """Clear the encrypted resume payload after successful resume."""
        self.resume_payload_encrypted = None
        self.save(update_fields=["resume_payload_encrypted", "updated_at"])

    def is_decidable(self) -> bool:
        """Return True if this request can be decided by a reviewer."""
        return self.status in self.DECIDABLE_STATUSES


class LangGraphCheckpoint(models.Model):
    """Serialized LangGraph checkpoint stored by thread/checkpoint id."""

    thread_id = models.CharField(max_length=255, db_index=True)
    checkpoint_ns = models.CharField(max_length=255, blank=True, default="")
    checkpoint_id = models.CharField(max_length=255, db_index=True)
    parent_checkpoint_id = models.CharField(max_length=255, blank=True, default="")
    config = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    checkpoint = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "djgent_langgraph_checkpoint"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["thread_id", "checkpoint_ns", "checkpoint_id"],
                name="djgent_lg_checkpoint_unique",
            )
        ]
        indexes = [
            models.Index(
                fields=["thread_id", "checkpoint_ns", "-created_at"],
                name="djgent_lg_ckpt_thread_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.thread_id}:{self.checkpoint_id}"


class LangGraphCheckpointWrite(models.Model):
    """Serialized LangGraph pending write linked to a checkpoint task."""

    thread_id = models.CharField(max_length=255, db_index=True)
    checkpoint_ns = models.CharField(max_length=255, blank=True, default="")
    checkpoint_id = models.CharField(max_length=255, db_index=True)
    task_id = models.CharField(max_length=255, db_index=True)
    idx = models.IntegerField()
    channel = models.CharField(max_length=255)
    value = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "djgent_langgraph_checkpoint_write"
        ordering = ["idx"]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "thread_id",
                    "checkpoint_ns",
                    "checkpoint_id",
                    "task_id",
                    "idx",
                ],
                name="djgent_lg_write_unique",
            )
        ]
        indexes = [
            models.Index(
                fields=["thread_id", "checkpoint_ns", "checkpoint_id"],
                name="djgent_lg_write_ckpt_idx",
            ),
        ]
