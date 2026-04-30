"""Decorators for creating tools easily."""

import inspect
from functools import wraps
from typing import Any, Callable, Dict, Optional, Tuple, Type, Union

from djgent.tools.base import Tool


class _FunctionTool(Tool):
    """Wrapper for function-based tools."""

    def __init__(
        self, func: Callable, name: Optional[str] = None, description: Optional[str] = None
    ):
        self._func = func
        self._signature = inspect.signature(func)
        self.name = name or func.__name__
        self.description = description or (func.__doc__ or "").strip().split("\n")[0]
        super().__init__()

    def _normalize_variadic_args(
        self, args: Tuple[Any, ...], kwargs: Dict[str, Any]
    ) -> Tuple[Tuple[Any, ...], Dict[str, Any]]:
        var_positional = next(
            (
                param
                for param in self._signature.parameters.values()
                if param.kind is inspect.Parameter.VAR_POSITIONAL
            ),
            None,
        )
        if var_positional is None or var_positional.name not in kwargs:
            return args, kwargs

        normalized_kwargs = dict(kwargs)
        variadic_values = normalized_kwargs.pop(var_positional.name)
        if isinstance(variadic_values, (list, tuple)):
            normalized_args = (*args, *variadic_values)
        else:
            normalized_args = (*args, variadic_values)
        return normalized_args, normalized_kwargs

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        normalized_args, normalized_kwargs = self._normalize_variadic_args(args, kwargs)
        return self._func(*normalized_args, **normalized_kwargs)

    def to_langchain(
        self,
        *,
        before_tool: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        after_tool: Optional[Callable[[str, Any], Any]] = None,
    ):
        """Convert function-based tools using the original function signature."""
        from langchain_core.tools import StructuredTool

        @wraps(self._func)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            normalized_args, normalized_kwargs = self._normalize_variadic_args(args, kwargs)
            bound = self._signature.bind_partial(*normalized_args, **normalized_kwargs)
            arguments = dict(bound.arguments)

            if before_tool:
                before_tool(self.name, arguments)

            result = self._func(*normalized_args, **normalized_kwargs)

            if after_tool:
                result = after_tool(self.name, result)

            return result

        wrapped.__signature__ = self._signature  # type: ignore[attr-defined]

        return StructuredTool.from_function(
            func=wrapped,
            name=self.name,
            description=self.description,
            args_schema=self.args_schema,
        )


def tool(
    func: Optional[Union[Callable, Type[Tool]]] = None,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
) -> Union[Tool, Type[Tool], Callable]:
    """
    Decorator to create/register a tool from a function or Tool subclass.

    Can be used as @tool or @tool(name="...", description="...")

    Args:
        func: The function or Tool subclass (when used without parentheses)
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

        @tool
        class WeatherTool(Tool):
            name = "weather"
            description = "Get weather"

            def _run(self, city: str) -> str:
                return f"Weather for {city}"
    """
    from djgent.tools.registry import ToolRegistry

    def _create_tool(fn: Callable) -> Tool:
        tool_instance = _FunctionTool(fn, name=name, description=description)
        tool_name = name or fn.__name__
        ToolRegistry.register(name=tool_name)(tool_instance)
        return tool_instance

    def _register_tool_class(tool_class: Type[Tool]) -> Type[Tool]:
        tool_name = name or getattr(tool_class, "name", None)
        if not isinstance(tool_name, str) or not tool_name.strip():
            raise ValueError(
                "Tool class decorator requires a non-empty 'name' attribute "
                "or @tool(name='...')."
            )

        if description is not None:
            tool_class.description = description

        ToolRegistry.register(name=tool_name)(tool_class)
        return tool_class

    def _decorate(obj: Union[Callable, Type[Tool]]) -> Union[Tool, Type[Tool]]:
        if isinstance(obj, type) and issubclass(obj, Tool):
            return _register_tool_class(obj)
        return _create_tool(obj)  # type: ignore[arg-type]

    if func is not None:
        return _decorate(func)

    return _decorate  # type: ignore[return-value]


def register_tool(
    cls: Optional[Union[Callable, Type[Tool]]] = None,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
) -> Union[Tool, Type[Tool], Callable]:
    """Backward-compatible alias for tool(). Prefer @tool for new code."""
    return tool(cls, name=name, description=description)
