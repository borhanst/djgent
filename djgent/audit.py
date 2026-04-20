"""Audit logging for Djgent agents."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from djgent.models import AuditLog
from django.conf import settings

logger = logging.getLogger(__name__)




class AuditEventType(str, Enum):
    """Types of audit events."""
    AGENT_RUN = "agent_run"
    TOOL_EXECUTION = "tool_execution"
    TOOL_APPROVAL = "tool_approval"
    MESSAGE_SENT = "message_sent"
    MESSAGE_RECEIVED = "message_received"
    ERROR = "error"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    AUTHENTICATION = "authentication"
    CONFIGURATION_CHANGE = "configuration_change"


class AuditLevel(str, Enum):
    """Audit event severity levels."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """
    Represents an audit event.
    
    Example:
        event = AuditEvent(
            event_type=AuditEventType.AGENT_RUN,
            level=AuditLevel.INFO,
            agent_name="my_agent",
            user_id=123,
            details={"input": "Hello", "output": "Hi there!"}
        )
        audit_logger.log(event)
    """
    event_type: AuditEventType
    level: AuditLevel = AuditLevel.INFO
    agent_name: Optional[str] = None
    thread_id: Optional[str] = None
    user_id: Optional[int] = None
    session_id: Optional[str] = None
    conversation_id: Optional[str] = None
    tool_name: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    duration_ms: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "level": self.level.value,
            "agent_name": self.agent_name,
            "thread_id": self.thread_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "conversation_id": self.conversation_id,
            "tool_name": self.tool_name,
            "details": self.details,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp.isoformat(),
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())


class AuditLogger:
    """
    Centralized audit logging for agent operations.
    
    Can be configured to log to various backends:
    - Django models (database)
    - File
    - External logging system
    
    Example:
        # Initialize logger
        audit = AuditLogger()
        
        # Log an event
        audit.log_agent_run(
            agent_name="my_agent",
            user_id=123,
            input_message="Hello",
            output_message="Hi there!"
        )
        
        # Query audit logs
        events = audit.query(
            agent_name="my_agent",
            event_type=AuditEventType.AGENT_RUN,
            limit=100
        )
    """

    def __init__(
        self,
        log_to_database: bool = True,
        log_to_console: bool = False,
        log_level: AuditLevel = AuditLevel.INFO,
    ):
        """
        Initialize audit logger.
        
        Args:
            log_to_database: Whether to log to Django database
            log_to_console: Whether to log to console
            log_level: Minimum level to log
        """
        self.log_to_database = log_to_database
        self.log_to_console = log_to_console
        self.log_level = log_level

    def _should_log(self, level: AuditLevel) -> bool:
        """Check if level should be logged."""
        levels = list(AuditLevel)
        return levels.index(level) >= levels.index(self.log_level)

    def log(self, event: AuditEvent) -> None:
        """
        Log an audit event.
        
        Args:
            event: The audit event to log
        """
        if not self._should_log(event.level):
            return

        # Log to console
        if self.log_to_console:
            self._log_to_console(event)

        # Log to database
        if self.log_to_database:
            self._log_to_database(event)

        # Log to standard logger
        self._log_to_logger(event)

    def _log_to_console(self, event: AuditEvent) -> None:
        """Log to console."""
        print(f"[AUDIT] {event.timestamp.isoformat()} | {event.event_type.value} | {event.level.value} | {event.agent_name or 'N/A'}")

    def _log_to_database(self, event: AuditEvent) -> None:
        """Log to Django database."""
        try:
            AuditLog.objects.create(
                event_id=event.event_id,
                event_type=event.event_type.value,
                level=event.level.value,
                agent_name=event.agent_name,
                thread_id=event.thread_id,
                user_id=event.user_id,
                session_id=event.session_id,
                conversation_id=event.conversation_id,
                tool_name=event.tool_name,
                details=event.details,
                error=event.error,
                duration_ms=event.duration_ms,
            )
        except Exception as e:
            logger.error(f"Failed to log audit event to database: {e}")

    def _log_to_logger(self, event: AuditEvent) -> None:
        """Log to Python logger."""
        log_data = event.to_dict()
        log_func = getattr(logger, event.level.value, logger.info)
        log_func(json.dumps(log_data))

    def log_agent_run(
        self,
        agent_name: str,
        input_message: str,
        output_message: Optional[str] = None,
        user_id: Optional[int] = None,
        thread_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        duration_ms: Optional[float] = None,
        error: Optional[str] = None,
    ) -> AuditEvent:
        """Log an agent run event."""
        event = AuditEvent(
            event_type=AuditEventType.AGENT_RUN,
            level=AuditLevel.ERROR if error else AuditLevel.INFO,
            agent_name=agent_name,
            user_id=user_id,
            thread_id=thread_id,
            conversation_id=conversation_id,
            details={
                "input": input_message,
                "output": output_message,
            },
            duration_ms=duration_ms,
            error=error,
        )
        self.log(event)
        return event

    def log_tool_execution(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        result: Any,
        agent_name: Optional[str] = None,
        user_id: Optional[int] = None,
        thread_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        duration_ms: Optional[float] = None,
        error: Optional[str] = None,
    ) -> AuditEvent:
        """Log a tool execution event."""
        # Sanitize arguments to remove sensitive data
        safe_arguments = self._sanitize_arguments(arguments)
        
        event = AuditEvent(
            event_type=AuditEventType.TOOL_EXECUTION,
            level=AuditLevel.ERROR if error else AuditLevel.INFO,
            agent_name=agent_name,
            tool_name=tool_name,
            user_id=user_id,
            thread_id=thread_id,
            conversation_id=conversation_id,
            details={
                "arguments": safe_arguments,
                "result_type": type(result).__name__,
            },
            duration_ms=duration_ms,
            error=error,
        )
        self.log(event)
        return event

    def log_tool_approval(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        approved: bool,
        agent_name: Optional[str] = None,
        user_id: Optional[int] = None,
        reason: Optional[str] = None,
    ) -> AuditEvent:
        """Log a tool approval event."""
        event = AuditEvent(
            event_type=AuditEventType.TOOL_APPROVAL,
            level=AuditLevel.INFO,
            agent_name=agent_name,
            tool_name=tool_name,
            user_id=user_id,
            details={
                "arguments": arguments,
                "approved": approved,
                "reason": reason,
            },
        )
        self.log(event)
        return event

    def log_rate_limit(
        self,
        agent_name: str,
        user_id: Optional[int] = None,
        limit_type: str = "minute",
    ) -> AuditEvent:
        """Log a rate limit exceeded event."""
        event = AuditEvent(
            event_type=AuditEventType.RATE_LIMIT_EXCEEDED,
            level=AuditLevel.WARNING,
            agent_name=agent_name,
            user_id=user_id,
            details={"limit_type": limit_type},
        )
        self.log(event)
        return event

    def _sanitize_arguments(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive data from arguments."""
        sensitive_keys = {'password', 'secret', 'token', 'api_key', 'key', 'auth'}
        sanitized = {}
        
        for key, value in arguments.items():
            if any(s in key.lower() for s in sensitive_keys):
                sanitized[key] = "***REDACTED***"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_arguments(value)
            else:
                sanitized[key] = value
        
        return sanitized

    def query(
        self,
        agent_name: Optional[str] = None,
        event_type: Optional[AuditEventType] = None,
        user_id: Optional[int] = None,
        thread_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[AuditEvent]:
        """
        Query audit events.
        
        Args:
            agent_name: Filter by agent name
            event_type: Filter by event type
            user_id: Filter by user ID
            thread_id: Filter by thread ID
            conversation_id: Filter by conversation ID
            start_time: Filter by start time
            end_time: Filter by end time
            limit: Maximum number of results
            
        Returns:
            List of matching audit events
        """
        if not self.log_to_database:
            return []

        queryset = AuditLog.objects.all()

        if agent_name:
            queryset = queryset.filter(agent_name=agent_name)
        if event_type:
            queryset = queryset.filter(event_type=event_type.value)
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        if thread_id:
            queryset = queryset.filter(thread_id=thread_id)
        if conversation_id:
            queryset = queryset.filter(conversation_id=conversation_id)
        if start_time:
            queryset = queryset.filter(timestamp__gte=start_time)
        if end_time:
            queryset = queryset.filter(timestamp__lte=end_time)

        queryset = queryset.order_by('-timestamp')[:limit]

        return [
            AuditEvent(
                event_type=AuditEventType(e.event_type),
                level=AuditLevel(e.level),
                agent_name=e.agent_name,
                thread_id=e.thread_id,
                user_id=e.user_id,
                session_id=e.session_id,
                conversation_id=e.conversation_id,
                tool_name=e.tool_name,
                details=e.details,
                error=e.error,
                duration_ms=e.duration_ms,
                timestamp=e.timestamp,
                event_id=e.event_id,
            )
            for e in queryset
        ]


def get_audit_logger() -> AuditLogger:
    """
    Get the global audit logger instance.
    
    Returns a lazy-initialized audit logger to avoid issues
    when importing before Django is set up.
    
    Example:
        audit = get_audit_logger()
        audit.log_agent_run(
            agent_name="my_agent",
            user_id=123,
            input_message="Hello"
        )
    """
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


# Lazy-initialized global audit logger instance
# Use get_audit_logger() to access
_audit_logger: Optional[AuditLogger] = None

__all__ = [
    "AuditEvent",
    "AuditEventType",
    "AuditLevel",
    "AuditLogger",
    "get_audit_logger",
]
