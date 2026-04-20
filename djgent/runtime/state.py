"""Durable execution state helpers."""

from __future__ import annotations

from typing import Any, Dict, Optional

from djgent.runtime.schemas import AgentExecutionState


class StateStore:
    """A thin persistence abstraction over Djgent memory backends."""

    def __init__(self, memory_backend: Optional[Any] = None):
        self.memory_backend = memory_backend
        self._memory_states: Dict[str, Dict[str, Any]] = {}

    def load(self, thread_id: str) -> AgentExecutionState:
        """Load state for a thread."""
        if self.memory_backend and hasattr(self.memory_backend, "get_state"):
            payload = self.memory_backend.get_state(thread_id)
        else:
            payload = self._memory_states.get(thread_id)
        return AgentExecutionState.from_dict(payload, thread_id=thread_id)

    def save(self, state: AgentExecutionState) -> AgentExecutionState:
        """Persist state for a thread."""
        payload = state.to_dict()
        if self.memory_backend and hasattr(self.memory_backend, "save_state"):
            self.memory_backend.save_state(state.thread_id, payload)
        else:
            self._memory_states[state.thread_id] = payload
        return state

    def clear(self, thread_id: str) -> None:
        """Remove persisted state for a thread."""
        if self.memory_backend and hasattr(self.memory_backend, "clear_state"):
            self.memory_backend.clear_state(thread_id)
            return
        self._memory_states.pop(thread_id, None)
