"""Decorators for creating tools easily."""

from typing import Any, Callable, Optional

from djgent.tools.base import Tool


class _FunctionTool(Tool):
    """Wrapper for function-based tools."""

    def __init__(self, func: Callable, name: Optional[str] = None, description: Optional[str] = None):
        self._func = func
        self.name = name or func.__name__
        self.description = description or (func.__doc__ or "").strip().split("\n")[0]
        super().__init__()

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        return self._func(*args, **kwargs)


def tool(
    func: Optional[Callable] = None,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
) -> Tool:
    """
    Decorator to create a tool from a function.

    Can be used as @tool or @tool(name="...", description="...")

    Args:
        func: The function to wrap (when used without parentheses)
        name: Optional name for the tool
        description: Optional description (defaults to function docstring first line)

    Returns:
        A Tool instance

    Example:
        @tool
        def search(query: str) -> str:
            '''Search the web'''
            return f"Results for {query}"

        @tool(name="web_search", description="Search the internet")
        def search(query: str) -> str:
            return f"Results for {query}"
    """
    from djgent.tools.registry import ToolRegistry

    def _create_tool(fn: Callable) -> Tool:
        tool_instance = _FunctionTool(fn, name=name, description=description)
        tool_name = name or fn.__name__
        ToolRegistry.register(name=tool_name)(tool_instance)
        return tool_instance

    if func is not None:
        return _create_tool(func)

    return _create_tool  # type: ignore
