"""Middleware hooks for Djgent agent execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List

from djgent.runtime.approvals import ApprovalRequiredError
from djgent.runtime.schemas import StreamEvent


@dataclass
class ExecutionContext:
    """Mutable execution context shared by middleware and runtime helpers."""

    agent_name: str
    thread_id: str
    input: str
    context: Dict[str, Any] = field(default_factory=dict)
    state: Dict[str, Any] = field(default_factory=dict)
    events: List[StreamEvent] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def emit(self, event: str, **data: Any) -> StreamEvent:
        """Record a stream event."""
        item = StreamEvent(event=event, data=data)
        self.events.append(item)
        return item


class AgentMiddleware:
    """Base middleware with no-op hooks."""

    def before_run(self, execution: ExecutionContext) -> None:
        """Hook called before the model invocation."""

    def after_run(self, execution: ExecutionContext, output: str) -> str:
        """Hook called after the model invocation."""
        return output

    def before_tool(
        self,
        execution: ExecutionContext,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> None:
        """Hook called before a tool is executed."""

    def after_tool(
        self,
        execution: ExecutionContext,
        tool_name: str,
        result: Any,
    ) -> Any:
        """Hook called after a tool is executed."""
        return result


class DynamicPromptMiddleware(AgentMiddleware):
    """Inject thread summaries and runtime context into the active prompt."""

    def before_run(self, execution: ExecutionContext) -> None:
        summary = execution.state.get("summary")
        prompt_parts = []

        if summary:
            prompt_parts.append(f"Conversation summary:\n{summary}")

        extra_prompt = execution.context.get("prompt_context")
        if extra_prompt:
            prompt_parts.append(str(extra_prompt))

        if prompt_parts:
            execution.metadata["dynamic_prompt"] = "\n\n".join(prompt_parts)


class ToolApprovalMiddleware(AgentMiddleware):
    """Interrupt risky tool calls until the caller explicitly approves them."""

    def before_tool(
        self,
        execution: ExecutionContext,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> None:
        approved = execution.context.get("approved_tools", {})
        if approved is True or approved.get(tool_name):
            return
        risky = execution.context.get("risky_tools", {})
        config = risky.get(tool_name)
        if not config:
            return

        reason = (
            config.get("reason") or f"Tool '{tool_name}' requires approval."
        )
        raise ApprovalRequiredError(
            tool_name=tool_name,
            arguments=arguments,
            reason=reason,
            thread_id=execution.thread_id,
        )


class OutputGuardrailMiddleware(AgentMiddleware):
    """Normalize empty or obviously invalid model outputs."""

    def after_run(self, execution: ExecutionContext, output: str) -> str:
        cleaned = (output or "").strip()
        if cleaned:
            return cleaned
        fallback = execution.context.get(
            "empty_output_fallback", "I processed your request."
        )
        execution.emit("guardrail.empty_output", fallback=fallback)
        return fallback


def apply_before_run(
    middleware: Iterable[AgentMiddleware], execution: ExecutionContext
) -> None:
    """Run before_run hooks."""
    for item in middleware:
        item.before_run(execution)


def apply_after_run(
    middleware: Iterable[AgentMiddleware],
    execution: ExecutionContext,
    output: str,
) -> str:
    """Run after_run hooks."""
    for item in middleware:
        output = item.after_run(execution, output)
    return output


def apply_before_tool(
    middleware: Iterable[AgentMiddleware],
    execution: ExecutionContext,
    tool_name: str,
    arguments: Dict[str, Any],
) -> None:
    """Run before_tool hooks."""
    for item in middleware:
        item.before_tool(execution, tool_name, arguments)


def apply_after_tool(
    middleware: Iterable[AgentMiddleware],
    execution: ExecutionContext,
    tool_name: str,
    result: Any,
) -> Any:
    """Run after_tool hooks."""
    for item in middleware:
        result = item.after_tool(execution, tool_name, result)
    return result
