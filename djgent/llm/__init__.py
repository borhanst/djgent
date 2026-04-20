"""LLM module for djgent."""

from djgent.llm.providers import get_llm, register_provider
from djgent.llm.config import LLMConfig

__all__ = [
    "get_llm",
    "register_provider",
    "LLMConfig",
]
