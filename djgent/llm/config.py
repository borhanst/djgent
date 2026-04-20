"""LLM configuration utilities."""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class LLMConfig:
    """Configuration for LLM providers."""

    provider: str
    model: str
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    extra_kwargs: Dict[str, Any] = None

    def __post_init__(self):
        if self.extra_kwargs is None:
            self.extra_kwargs = {}

    def to_kwargs(self) -> Dict[str, Any]:
        """Convert config to kwargs for LLM constructor."""
        kwargs = {
            "model": self.model,
            "temperature": self.temperature,
        }

        if self.max_tokens:
            kwargs["max_tokens"] = self.max_tokens

        if self.api_key:
            kwargs["api_key"] = self.api_key

        if self.base_url:
            kwargs["base_url"] = self.base_url

        kwargs.update(self.extra_kwargs)
        return kwargs
