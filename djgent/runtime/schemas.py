"""Runtime schemas for Djgent agent execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Type


@dataclass
class StreamEvent:
    """A coarse-grained execution event emitted during agent runs."""

    event: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ApprovalRequest:
    """Represents a pending approval for a risky tool invocation."""

    tool_name: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    thread_id: Optional[str] = None


@dataclass
class AgentResult:
    """Normalized result returned by advanced execution APIs."""

    output: str
    messages: List[Any] = field(default_factory=list)
    structured_response: Optional[Any] = None
    state: Dict[str, Any] = field(default_factory=dict)
    events: List[StreamEvent] = field(default_factory=list)


@dataclass
class AgentExecutionState:
    """Durable per-thread state used across runs."""

    thread_id: str
    values: Dict[str, Any] = field(default_factory=dict)
    summary: Optional[str] = None
    paused_tool_name: Optional[str] = None
    paused_tool_arguments: Dict[str, Any] = field(default_factory=dict)
    status: str = "idle"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the state to a JSON-compatible dict."""
        return {
            "thread_id": self.thread_id,
            "values": self.values,
            "summary": self.summary,
            "paused_tool_name": self.paused_tool_name,
            "paused_tool_arguments": self.paused_tool_arguments,
            "status": self.status,
        }

    @classmethod
    def from_dict(
        cls,
        payload: Optional[Dict[str, Any]],
        *,
        thread_id: str,
    ) -> "AgentExecutionState":
        """Hydrate state from a JSON-compatible dict."""
        payload = payload or {}
        return cls(
            thread_id=payload.get("thread_id", thread_id),
            values=payload.get("values", {}) or {},
            summary=payload.get("summary"),
            paused_tool_name=payload.get("paused_tool_name"),
            paused_tool_arguments=payload.get("paused_tool_arguments", {}) or {},
            status=payload.get("status", "idle"),
        )


def iter_schema_fields(schema: Any) -> Iterable[str]:
    """Return field names for dataclass, TypedDict-like, or Pydantic schemas."""
    if schema is None:
        return []

    if hasattr(schema, "model_fields"):
        return list(schema.model_fields.keys())

    if hasattr(schema, "__dataclass_fields__"):
        return list(schema.__dataclass_fields__.keys())

    annotations = getattr(schema, "__annotations__", {})
    return list(annotations.keys())


def schema_name(schema: Optional[Type[Any]]) -> Optional[str]:
    """Return a friendly schema name."""
    if schema is None:
        return None
    return getattr(schema, "__name__", schema.__class__.__name__)
