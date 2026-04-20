"""Human-in-the-loop persistence and notification helpers."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse
from django.utils import timezone

from djgent.utils.helpers import merge_settings

DJGENT_HITL_KEYS = {
    "notify_email",
    "site_url",
    "site_owner_emails",
}


def human_in_the_loop_config(
    langchain_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    resolved = dict((langchain_config or {}).get("human_in_the_loop") or {})
    return resolved if resolved.get("enabled", True) is not False else {}


def is_human_in_the_loop_enabled(
    langchain_config: Optional[Dict[str, Any]] = None,
) -> bool:
    config = human_in_the_loop_config(langchain_config)
    return bool(config and config.get("interrupt_on"))


def sanitize_hitl_config(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Return kwargs accepted by LangChain HumanInTheLoopMiddleware."""
    clean = {}
    if "interrupt_on" in spec:
        clean["interrupt_on"] = spec["interrupt_on"]
    if "description_prefix" in spec:
        clean["description_prefix"] = spec["description_prefix"]
    return clean


def site_owner_emails(hitl_config: Optional[Dict[str, Any]] = None) -> List[str]:
    config = hitl_config or {}
    values: Iterable[Any] = config.get("site_owner_emails") or []
    if not values:
        values = merge_settings().get("SITE_OWNER_EMAILS", []) or []
    if not values:
        values = [email for _, email in getattr(settings, "ADMINS", [])]
    return [str(email) for email in values if str(email).strip()]


def default_approval_decisions(action_requests: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    return [{"type": "approve"} for _ in action_requests]


def normalize_decisions(
    action_requests: List[Dict[str, Any]],
    decisions: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    resolved = decisions or default_approval_decisions(action_requests)
    if len(resolved) != len(action_requests):
        raise ValueError(
            "Human interaction decisions must match action request count."
        )
    return resolved


def notification_url(request_id: Any, site_url: str = "") -> str:
    try:
        path = reverse(
            "admin:djgent_humaninteractionrequest_change",
            args=[request_id],
        )
    except Exception:
        path = f"/admin/djgent/humaninteractionrequest/{request_id}/change/"
    return f"{site_url.rstrip('/')}{path}" if site_url else path


def persist_human_interaction_request(
    *,
    agent_name: str,
    thread_id: str,
    conversation: Any = None,
    requesting_user: Any = None,
    hitl_config: Optional[Dict[str, Any]] = None,
    action_requests: Optional[List[Dict[str, Any]]] = None,
    review_configs: Optional[List[Dict[str, Any]]] = None,
) -> Any:
    from djgent.models import HumanInteractionRequest

    config = hitl_config or {}
    emails = site_owner_emails(config)
    request = HumanInteractionRequest.objects.create(
        agent_name=agent_name,
        thread_id=thread_id,
        conversation=conversation,
        requesting_user=(
            requesting_user
            if getattr(requesting_user, "is_authenticated", False)
            else None
        ),
        site_owner_emails=emails,
        action_requests=action_requests or [],
        review_configs=review_configs or [],
    )
    if config.get("notify_email", True):
        notify_site_owners(request, config)
    return request


def notify_site_owners(request: Any, hitl_config: Optional[Dict[str, Any]] = None) -> None:
    config = hitl_config or {}
    recipients = list(request.site_owner_emails or [])
    if not recipients:
        return

    site_url = str(config.get("site_url") or "")
    url = notification_url(request.id, site_url=site_url)
    action_lines = []
    for action in request.action_requests:
        name = action.get("name") or action.get("tool") or "unknown"
        args = action.get("arguments", action.get("args", {}))
        action_lines.append(f"- {name}: {args}")
    body = "\n".join(
        [
            "Djgent tool execution requires site owner review.",
            "",
            f"Request: {request.id}",
            f"Agent: {request.agent_name}",
            f"Thread: {request.thread_id}",
            "",
            "Actions:",
            "\n".join(action_lines) or "- No action details provided",
            "",
            f"Review: {url}",
        ]
    )

    try:
        send_mail(
            subject=f"Djgent approval needed: {request.agent_name}",
            message=body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            recipient_list=recipients,
            fail_silently=False,
        )
    except Exception as exc:
        request.notification_error = str(exc)
        request.save(update_fields=["notification_error", "updated_at"])
        return

    request.emailed_at = timezone.now()
    request.save(update_fields=["emailed_at", "updated_at"])


def extract_interrupt_payload(result: Any) -> Optional[Dict[str, Any]]:
    """Normalize LangGraph interrupt outputs into action/review lists."""
    interrupts = getattr(result, "interrupts", None)
    if interrupts:
        value = getattr(interrupts[0], "value", interrupts[0])
        return dict(value or {})

    if isinstance(result, dict):
        raw = result.get("__interrupt__")
        if raw:
            first = raw[0] if isinstance(raw, (list, tuple)) else raw
            value = getattr(first, "value", first)
            return dict(value or {})

    return None
