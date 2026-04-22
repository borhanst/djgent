"""Helpers for configuring LangChain built-in middleware from Djgent settings."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple

from djgent.exceptions import ConfigurationError
from djgent.utils.helpers import merge_settings

MIDDLEWARE_CLASS_MAP = {
    "summarization": "SummarizationMiddleware",
    "model_retry": "ModelRetryMiddleware",
    "tool_retry": "ToolRetryMiddleware",
    "model_fallback": "ModelFallbackMiddleware",
    "model_call_limit": "ModelCallLimitMiddleware",
    "tool_call_limit": "ToolCallLimitMiddleware",
    "tool_selector": "LLMToolSelectorMiddleware",
    "context_editing": "ContextEditingMiddleware",
}


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge dictionaries without mutating either input."""
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(merged.get(key), dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _normalize_specs(spec: Any) -> List[Dict[str, Any]]:
    """Normalize a middleware config section into a list of constructor kwargs."""
    if spec in (None, False):
        return []
    if spec is True:
        return [{}]
    if isinstance(spec, dict):
        if spec.get("enabled") is False:
            return []
        return [{k: v for k, v in spec.items() if k != "enabled"}]
    if isinstance(spec, list):
        normalized: List[Dict[str, Any]] = []
        for item in spec:
            normalized.extend(_normalize_specs(item))
        return normalized
    raise ConfigurationError(
        "LANGCHAIN_MIDDLEWARE sections must be a bool, dict, or list of dicts."
    )


def _load_middleware_class(class_name: str) -> Any:
    """Load a LangChain middleware class lazily."""
    try:
        from langchain.agents import middleware as lc_middleware
    except ImportError as exc:
        raise ConfigurationError(
            "LangChain middleware support requires a LangChain version that "
            "provides 'langchain.agents.middleware'."
        ) from exc

    try:
        return getattr(lc_middleware, class_name)
    except AttributeError as exc:
        raise ConfigurationError(f"Installed LangChain does not provide '{class_name}'.") from exc


def resolve_langchain_middleware_config(
    override: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Merge project defaults, Django settings, and per-agent overrides."""
    settings_config = merge_settings().get("LANGCHAIN_MIDDLEWARE", {}) or {}
    return _deep_merge(settings_config, override or {})


def has_enabled_langchain_middleware(
    config: Optional[Dict[str, Any]],
    name: str,
) -> bool:
    """Return True when a named middleware section is enabled."""
    if not config:
        return False
    specs = _normalize_specs(config.get(name))
    return bool(specs)


def build_langchain_middleware(
    *,
    config: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Any], Optional[Any]]:
    """Build LangChain built-in middleware instances from Djgent config."""
    resolved = resolve_langchain_middleware_config(config)
    instances: List[Any] = []
    checkpointer = resolved.get("checkpointer")

    hitl_specs = _normalize_specs(resolved.get("human_in_the_loop"))
    if hitl_specs:
        raise ConfigurationError(
            "LANGCHAIN_MIDDLEWARE['human_in_the_loop'] is not wired into Djgent "
            "yet because it requires an interrupt/resume flow migration."
        )

    for section, class_name in MIDDLEWARE_CLASS_MAP.items():
        specs = _normalize_specs(resolved.get(section))
        if not specs:
            continue
        middleware_class = _load_middleware_class(class_name)
        for spec in specs:
            instances.append(middleware_class(**spec))

    return instances, checkpointer
