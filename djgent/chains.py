"""
Chains module for djgent.

This module provides chain functionality for sequential tool/agent execution.
Note: LangGraph already provides built-in chain concepts for agent flows.

For most use cases, use LangGraph's StateGraph instead.
"""

from __future__ import annotations

from typing import Any, Callable, List, TypeVar

T = TypeVar('T')


class Chain:
    """
    Simple chain for sequential execution of callable items.
    
    Example:
        chain = Chain()
        chain.add(step1)
        chain.add(step2)
        result = chain.execute(input)
    """

    def __init__(self) -> None:
        self._steps: List[Callable[..., Any]] = []

    def add(self, step: Callable[..., Any]) -> "Chain":
        """Add a step to the chain."""
        self._steps.append(step)
        return self

    def execute(self, input_data: Any, **kwargs: Any) -> Any:
        """Execute all steps in sequence."""
        result = input_data
        for step in self._steps:
            result = step(result, **kwargs)
        return result

    def __len__(self) -> int:
        return len(self._steps)

    def clear(self) -> None:
        """Clear all steps from the chain."""
        self._steps.clear()


__all__ = [
    "Chain",
]
