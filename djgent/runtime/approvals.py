"""Approval primitives for risky tool execution."""

from __future__ import annotations

from typing import Any, Dict, Optional

from djgent.runtime.schemas import ApprovalRequest


class ApprovalRequiredError(RuntimeError):
    """Raised when a tool invocation requires user approval."""

    def __init__(
        self,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        reason: str = "",
        thread_id: Optional[str] = None,
    ) -> None:
        self.request = ApprovalRequest(
            tool_name=tool_name,
            arguments=arguments or {},
            reason=reason,
            thread_id=thread_id,
        )
        message = reason or f"Approval required before running tool '{tool_name}'."
        super().__init__(message)
