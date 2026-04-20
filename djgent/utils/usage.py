"""Helpers for extracting token usage and estimating LLM cost."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Optional

from django.conf import settings
from langchain_core.messages import AIMessage


def _coerce_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _first_dict(*candidates: Any) -> Dict[str, Any]:
    for candidate in candidates:
        if isinstance(candidate, dict):
            return candidate
    return {}


def _find_ai_message(result: Any, output_messages: list[Any]) -> Optional[AIMessage]:
    if isinstance(result, AIMessage):
        return result

    for message in reversed(output_messages or []):
        if isinstance(message, AIMessage):
            return message

    if isinstance(result, dict):
        for message in reversed(result.get("messages", []) or []):
            if isinstance(message, AIMessage):
                return message

    return None


def estimate_cost(
    *,
    llm_identifier: Optional[str],
    model_name: Optional[str],
    input_tokens: int,
    output_tokens: int,
) -> Decimal:
    """Estimate request cost from DJGENT['MODEL_PRICING'] if configured."""
    pricing_map = getattr(settings, "DJGENT", {}).get("MODEL_PRICING", {})
    pricing = None
    for key in (llm_identifier, model_name):
        if key and key in pricing_map:
            pricing = pricing_map[key]
            break

    if not pricing:
        return Decimal("0")

    input_rate = Decimal(str(pricing.get("input_cost_per_1m", 0)))
    output_rate = Decimal(str(pricing.get("output_cost_per_1m", 0)))

    input_cost = (Decimal(input_tokens) / Decimal(1_000_000)) * input_rate
    output_cost = (Decimal(output_tokens) / Decimal(1_000_000)) * output_rate
    return (input_cost + output_cost).quantize(Decimal("0.00000001"))


def extract_usage_details(
    result: Any,
    output_messages: list[Any],
    *,
    llm_identifier: Optional[str] = None,
) -> Dict[str, Any]:
    """Extract normalized usage metadata from a LangChain result."""
    ai_message = _find_ai_message(result, output_messages)
    if not ai_message:
        return {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "estimated_cost": Decimal("0"),
            "model_name": None,
            "llm_identifier": llm_identifier,
            "usage_metadata": {},
            "response_metadata": {},
        }

    response_metadata = _first_dict(getattr(ai_message, "response_metadata", None))
    usage_metadata = _first_dict(
        getattr(ai_message, "usage_metadata", None),
        response_metadata.get("token_usage"),
        response_metadata.get("usage"),
        response_metadata.get("usage_metadata"),
    )

    input_tokens = _coerce_int(
        usage_metadata.get("input_tokens", usage_metadata.get("prompt_tokens"))
    )
    output_tokens = _coerce_int(
        usage_metadata.get(
            "output_tokens",
            usage_metadata.get("completion_tokens"),
        )
    )
    total_tokens = _coerce_int(
        usage_metadata.get("total_tokens", input_tokens + output_tokens)
    )
    model_name = (
        response_metadata.get("model_name")
        or response_metadata.get("model")
        or getattr(ai_message, "name", None)
    )

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "estimated_cost": estimate_cost(
            llm_identifier=llm_identifier,
            model_name=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        ),
        "model_name": model_name,
        "llm_identifier": llm_identifier or model_name,
        "usage_metadata": usage_metadata,
        "response_metadata": response_metadata,
    }
