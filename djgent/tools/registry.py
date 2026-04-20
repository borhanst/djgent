"""Tool registry for managing and discovering tools."""

from typing import Any, Callable, Dict, List, Optional, Type, Union

from djgent.exceptions import RegistryError
from djgent.tools.base import Tool


class ToolRegistry:
    """
    Central registry for all available tools.

    Provides methods to register, retrieve, and discover tools.
    """

    _tools: Dict[str, Union[Tool, Type[Tool], Callable]] = {}
    _discovered: bool = False

    @classmethod
    def register(
        cls,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Callable:
        """
        Decorator to register a tool function or class.

        Args:
            name: Optional name for the tool (defaults to function name)
            description: Optional description for the tool

        Returns:
            The decorator function
        """

        def decorator(obj: Union[Tool, Type[Tool], Callable]) -> Union[Tool, Type[Tool], Callable]:
            tool_name = name or obj.__name__  # type: ignore
            tool_desc = description or (obj.__doc__ or "").strip().split("\n")[0]  # type: ignore

            cls._tools[tool_name] = obj
            return obj

        return decorator

    @classmethod
    def get(cls, name: str) -> Union[Tool, Type[Tool], Callable]:
        """
        Get a tool by name.

        Args:
            name: The name of the tool

        Returns:
            The tool instance, class, or function

        Raises:
            RegistryError: If the tool is not found
        """
        if name not in cls._tools:
            raise RegistryError(f"Tool '{name}' not found. Available tools: {list(cls._tools.keys())}")
        return cls._tools[name]

    @classmethod
    def get_tool_instance(cls, name: str, **kwargs: Any) -> Tool:
        """
        Get an instance of a tool by name.

        Args:
            name: The name of the tool
            **kwargs: Arguments to pass to the tool constructor

        Returns:
            An instance of the tool

        Raises:
            RegistryError: If the tool is not found or cannot be instantiated
        """
        tool = cls.get(name)

        if isinstance(tool, Tool):
            return tool
        elif isinstance(tool, type) and issubclass(tool, Tool):
            return tool(**kwargs)
        else:
            # It's a function, wrap it
            from djgent.tools.decorators import _FunctionTool

            return _FunctionTool(tool, name=name)  # type: ignore

    @classmethod
    def list_tools(cls) -> List[str]:
        """
        List all registered tool names.

        Returns:
            List of tool names
        """
        return list(cls._tools.keys())

    @classmethod
    def has_tool(cls, name: str) -> bool:
        """
        Check if a tool is registered.

        Args:
            name: The name of the tool

        Returns:
            True if the tool exists, False otherwise
        """
        return name in cls._tools

    @classmethod
    def auto_discover(cls) -> None:
        """
        Auto-discover tools from installed apps.

        Scans each installed Django app for a 'tools.py' module
        and imports it to trigger tool registration.
        """
        if cls._discovered:
            return

        from django.apps import apps

        for app_config in apps.get_app_configs():
            try:
                module_name = f"{app_config.name}.tools"
                __import__(module_name)
            except ImportError:
                pass  # App doesn't have tools module

        cls._discovered = True

    @classmethod
    def clear(cls) -> None:
        """Clear all registered tools."""
        cls._tools.clear()
        cls._discovered = False
