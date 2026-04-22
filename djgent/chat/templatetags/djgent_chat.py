from typing import Any

from django import template
from django.urls import NoReverseMatch, reverse

from djgent.chat.views import _chat_settings

register = template.Library()


def _resolver_names(request: Any) -> list[str]:
    resolver_match = getattr(request, "resolver_match", None)
    if resolver_match is None:
        return []

    names = list(getattr(resolver_match, "namespaces", []) or [])
    namespace = getattr(resolver_match, "namespace", "")
    app_name = getattr(resolver_match, "app_name", "")
    if namespace:
        names.append(namespace)
    if app_name:
        names.append(app_name)
    return names


@register.inclusion_tag("djgent/chat_bubble.html", takes_context=True)
def djgent_chat_bubble(
    context: dict[str, Any],
    title: str | None = None,
    label: str | None = None,
) -> dict[str, Any]:
    request = context.get("request")
    chat_settings = _chat_settings()

    if not request or not chat_settings["bubble_enabled"]:
        return {"enabled": False}

    resolver_names = _resolver_names(request)
    if "djgent_chat" in resolver_names or "admin" in resolver_names:
        return {"enabled": False}

    try:
        iframe_url = reverse("djgent_chat:embed")
        full_chat_url = reverse("djgent_chat:home")
    except NoReverseMatch:
        return {"enabled": False}

    return {
        "enabled": True,
        "bubble_title": title or chat_settings["bubble_title"],
        "bubble_label": label or chat_settings["bubble_label"],
        "bubble_position": chat_settings["bubble_position"],
        "bubble_panel_width": chat_settings["bubble_panel_width"],
        "bubble_panel_mobile_height": chat_settings["bubble_panel_mobile_height"],
        "iframe_url": iframe_url,
        "full_chat_url": full_chat_url,
    }
