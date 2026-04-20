"""Middleware hooks for Djgent agent execution."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

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


class AuditMiddleware(AgentMiddleware):
    """Audit agent runs and tool executions through AuditLogger."""

    def __init__(
        self,
        *,
        log_input_output: Optional[bool] = None,
        log_tool_arguments: Optional[bool] = None,
        log_tool_results: Optional[bool] = None,
    ):
        from djgent.audit import _audit_settings

        config = _audit_settings()
        self.log_input_output = (
            bool(config.get("LOG_INPUT_OUTPUT", True))
            if log_input_output is None
            else log_input_output
        )
        self.log_tool_arguments = (
            bool(config.get("LOG_TOOL_ARGUMENTS", True))
            if log_tool_arguments is None
            else log_tool_arguments
        )
        self.log_tool_results = (
            bool(config.get("LOG_TOOL_RESULTS", False))
            if log_tool_results is None
            else log_tool_results
        )

    def before_run(self, execution: ExecutionContext) -> None:
        """Record run start time for duration logging."""
        execution.metadata["audit_run_start"] = time.perf_counter()

    def after_run(self, execution: ExecutionContext, output: str) -> str:
        """Log a completed agent run."""
        from djgent.audit import get_audit_logger

        get_audit_logger().log_agent_run(
            agent_name=execution.agent_name,
            input_message=execution.input if self.log_input_output else "",
            output_message=output if self.log_input_output else None,
            user_id=self._user_id(execution),
            thread_id=execution.thread_id,
            conversation_id=self._conversation_id(execution),
            duration_ms=self._duration_ms(
                execution.metadata.get("audit_run_start")
            ),
        )
        return output

    def before_tool(
        self,
        execution: ExecutionContext,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> None:
        """Record tool start time and arguments for audit logging."""
        starts = execution.metadata.setdefault("audit_tool_starts", {})
        starts[tool_name] = time.perf_counter()
        if self.log_tool_arguments:
            args = execution.metadata.setdefault("audit_tool_arguments", {})
            args[tool_name] = self._safe_tool_arguments(arguments)

    def after_tool(
        self,
        execution: ExecutionContext,
        tool_name: str,
        result: Any,
    ) -> Any:
        """Log a completed tool execution."""
        from djgent.audit import get_audit_logger

        starts = execution.metadata.get("audit_tool_starts", {})
        arguments = {}
        if self.log_tool_arguments:
            arguments = execution.metadata.get("audit_tool_arguments", {}).get(
                tool_name, {}
            )

        get_audit_logger().log_tool_execution(
            tool_name=tool_name,
            arguments=arguments,
            result=result,
            agent_name=execution.agent_name,
            user_id=self._user_id(execution),
            thread_id=execution.thread_id,
            conversation_id=self._conversation_id(execution),
            duration_ms=self._duration_ms(starts.get(tool_name)),
            log_result=self.log_tool_results,
        )
        return result

    def log_failed_run(self, execution: ExecutionContext, error: Exception) -> None:
        """Log a failed agent run from the agent exception path."""
        from djgent.audit import get_audit_logger

        get_audit_logger().log_agent_run(
            agent_name=execution.agent_name,
            input_message=execution.input if self.log_input_output else "",
            output_message=None,
            user_id=self._user_id(execution),
            thread_id=execution.thread_id,
            conversation_id=self._conversation_id(execution),
            duration_ms=self._duration_ms(
                execution.metadata.get("audit_run_start")
            ),
            error=str(error),
        )

    def log_tool_approval(
        self,
        execution: ExecutionContext,
        tool_name: str,
        arguments: Dict[str, Any],
        *,
        approved: bool,
        reason: Optional[str] = None,
    ) -> None:
        """Log a tool approval decision/interruption."""
        from djgent.audit import get_audit_logger

        get_audit_logger().log_tool_approval(
            tool_name=tool_name,
            arguments=arguments if self.log_tool_arguments else {},
            approved=approved,
            agent_name=execution.agent_name,
            user_id=self._user_id(execution),
            thread_id=execution.thread_id,
            conversation_id=self._conversation_id(execution),
            reason=reason,
        )

    def log_rate_limit(self, execution: ExecutionContext, error: Exception) -> None:
        """Log a rate-limit failure."""
        from djgent.audit import get_audit_logger

        limit_type = getattr(error, "limit_type", None) or str(error)
        get_audit_logger().log_rate_limit(
            agent_name=execution.agent_name,
            user_id=self._user_id(execution),
            limit_type=limit_type,
        )

    def _duration_ms(self, start: Optional[float]) -> Optional[float]:
        if start is None:
            return None
        return (time.perf_counter() - start) * 1000

    def _conversation_id(self, execution: ExecutionContext) -> Optional[str]:
        value = execution.metadata.get("conversation_id")
        if value:
            return str(value)
        django_context = execution.context.get("django")
        conversation = getattr(django_context, "conversation", None)
        if conversation is not None:
            conversation_id = getattr(conversation, "id", conversation)
            return str(conversation_id)
        return None

    def _user_id(self, execution: ExecutionContext) -> Optional[int]:
        django_context = execution.context.get("django")
        user_id = getattr(django_context, "user_id", None)
        if user_id is not None:
            return user_id
        return execution.metadata.get("user_id")

    def _safe_tool_arguments(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Store only audit-safe tool argument values in execution metadata."""
        from djgent.audit import get_audit_logger

        return get_audit_logger()._sanitize_arguments(arguments)


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
