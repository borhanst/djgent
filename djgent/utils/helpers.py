"""Helper utilities for djgent."""

from typing import Any, Dict

from django.conf import settings


def get_djent_setting(name: str, default: Any = None) -> Any:
    """
    Get a djgent setting from Django settings.

    Args:
        name: Setting name
        default: Default value if not found

    Returns:
        The setting value
    """
    djgent_settings = getattr(settings, "DJGENT", {})
    return djgent_settings.get(name, default)


def merge_settings() -> Dict[str, Any]:
    """
    Merge default settings with user settings.

    Returns:
        Merged settings dictionary
    """
    from djgent.settings import DJGENT_DEFAULTS

    user_settings = getattr(settings, "DJGENT", {})
    merged = DJGENT_DEFAULTS.copy()
    merged.update(user_settings)

    # Deep merge API_KEYS
    if "API_KEYS" in user_settings:
        merged["API_KEYS"] = {**DJGENT_DEFAULTS.get("API_KEYS", {}), **user_settings.get("API_KEYS", {})}

    return merged


def get_llm_config() -> Dict[str, Any]:
    """
    Get LLM configuration from settings.

    Returns:
        LLM configuration dictionary
    """
    djgent_settings = merge_settings()
    return {
        "provider_string": djgent_settings.get("DEFAULT_LLM", "openai:gpt-4o-mini"),
        "api_keys": djgent_settings.get("API_KEYS", {}),
    }
