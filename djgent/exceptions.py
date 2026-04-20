"""Custom exceptions for djgent."""

from __future__ import annotations

from typing import Any, Optional


class DjgentError(Exception):
    """Base exception for djgent."""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class AgentError(DjgentError):
    """Exception raised for agent-related errors."""

    def __init__(
        self,
        message: str,
        agent_name: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        self.agent_name = agent_name
        details = kwargs.pop("details", {})
        details["agent_name"] = agent_name
        super().__init__(message, details)


class ToolError(DjgentError):
    """Exception raised for tool-related errors."""

    def __init__(
        self,
        message: str,
        tool_name: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        self.tool_name = tool_name
        details = kwargs.pop("details", {})
        details["tool_name"] = tool_name
        super().__init__(message, details)


class LLMError(DjgentError):
    """Exception raised for LLM-related errors."""

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        self.provider = provider
        self.model = model
        details = kwargs.pop("details", {})
        details["provider"] = provider
        details["model"] = model
        super().__init__(message, details)


class RegistryError(DjgentError):
    """Exception raised for registry-related errors."""

    def __init__(
        self,
        message: str,
        registry_name: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        self.registry_name = registry_name
        details = kwargs.pop("details", {})
        details["registry_name"] = registry_name
        super().__init__(message, details)


class MemoryError(DjgentError):
    """Exception raised for memory-related errors."""

    def __init__(
        self,
        message: str,
        backend: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        self.backend = backend
        details = kwargs.pop("details", {})
        details["backend"] = backend
        super().__init__(message, details)


class RateLimitError(DjgentError):
    """Exception raised when rate limit is exceeded."""

    def __init__(
        self,
        message: str,
        limit_type: Optional[str] = None,
        retry_after: Optional[int] = None,
        **kwargs: Any,
    ) -> None:
        self.limit_type = limit_type
        self.retry_after = retry_after
        details = kwargs.pop("details", {})
        details["limit_type"] = limit_type
        details["retry_after"] = retry_after
        super().__init__(message, details)


class ValidationError(DjgentError):
    """Exception raised for validation errors."""

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        self.field = field
        self.value = value
        details = kwargs.pop("details", {})
        details["field"] = field
        details["value"] = str(value) if value is not None else None
        super().__init__(message, details)


class ConfigurationError(DjgentError):
    """Exception raised for configuration errors."""

    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        self.config_key = config_key
        details = kwargs.pop("details", {})
        details["config_key"] = config_key
        super().__init__(message, details)
