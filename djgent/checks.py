"""Django system checks for djgent configuration."""

from __future__ import annotations

from typing import Any, List

from django.conf import settings
from django.core.checks import CheckMessage, Error, Warning, register


@register()
def check_hitl_reviewer_policy(app_configs: Any, **kwargs: Any) -> List[CheckMessage]:
    """Fail when protected tools are configured but no reviewer policy exists.

    This is a fail-closed check: if human-in-the-loop is enabled with protected
    tools, the system must have a reviewer policy configured. Without one,
    protected tool calls would block indefinitely.
    """
    errors: List[CheckMessage] = []

    djgent_config = getattr(settings, "DJGENT", {})
    hitl_config = djgent_config.get("HUMAN_IN_THE_LOOP", {})

    if not hitl_config:
        return errors

    protected_tools = hitl_config.get("PROTECTED_TOOLS", {})
    if not protected_tools:
        return errors

    # Check that reviewer policy exists
    reviewer_policy = hitl_config.get("REVIEWER_POLICY", {})
    if not reviewer_policy:
        errors.append(
            Error(
                "HUMAN_IN_THE_LOOP.PROTECTED_TOOLS is configured but "
                "HUMAN_IN_THE_LOOP.REVIEWER_POLICY is missing.",
                hint=(
                    "Add a REVIEWER_POLICY to DJGENT['HUMAN_IN_THE_LOOP'] with "
                    "at least 'mode' and 'site_owner_emails' keys. "
                    "Example: REVIEWER_POLICY = {'mode': 'admin', 'site_owner_emails': ['admin@example.com']}"
                ),
                id="djgent.E001",
            )
        )

    # Check that site_owner_emails is configured
    site_owner_emails = hitl_config.get("site_owner_emails", [])
    if not site_owner_emails and not reviewer_policy.get("site_owner_emails"):
        errors.append(
            Warning(
                "HUMAN_IN_THE_LOOP has protected tools but no site_owner_emails configured.",
                hint=(
                    "Add 'site_owner_emails' to DJGENT['HUMAN_IN_THE_LOOP'] "
                    "to receive email notifications for protected tool reviews."
                ),
                id="djgent.W001",
            )
        )

    return errors


@register()
def check_hitl_durable_persistence(app_configs: Any, **kwargs: Any) -> List[CheckMessage]:
    """Fail when HITL protected tools are configured but durable persistence is missing.

    First-class human interaction requires database-backed persistence for
    request storage, encrypted resume payloads, and same-conversation final
    responses. In-memory backends cannot safely support the HITL workflow.
    """
    errors: List[CheckMessage] = []

    djgent_config = getattr(settings, "DJGENT", {})
    hitl_config = djgent_config.get("HUMAN_IN_THE_LOOP", {})

    if not hitl_config:
        return errors

    protected_tools = hitl_config.get("PROTECTED_TOOLS", {})
    if not protected_tools:
        return errors

    # Check that database-backed persistence is available
    memory_backend = djgent_config.get("MEMORY_BACKEND", "memory")
    if memory_backend == "memory":
        errors.append(
            Error(
                "HUMAN_IN_THE_LOOP.PROTECTED_TOOLS is configured but "
                "MEMORY_BACKEND is set to 'memory' (in-memory).",
                hint=(
                    "First-class human interaction requires durable "
                    "database-backed persistence. Set DJGENT['MEMORY_BACKEND'] "
                    "to 'database' to enable HITL workflows."
                ),
                id="djgent.E002",
            )
        )

    return errors


@register()
def check_hitl_disabled_with_protected_tools(
    app_configs: Any, **kwargs: Any
) -> List[CheckMessage]:
    """Fail when HITL is explicitly disabled but protected tools are configured.

    Protected tools require human interaction review. If HITL is explicitly
    disabled, protected operations would be blocked indefinitely or bypassed.
    """
    errors: List[CheckMessage] = []

    djgent_config = getattr(settings, "DJGENT", {})
    hitl_config = djgent_config.get("HUMAN_IN_THE_LOOP", {})

    if not hitl_config:
        return errors

    protected_tools = hitl_config.get("PROTECTED_TOOLS", {})
    if not protected_tools:
        return errors

    # Check if HITL is explicitly disabled
    if hitl_config.get("enabled") is False:
        errors.append(
            Error(
                "HUMAN_IN_THE_LOOP.PROTECTED_TOOLS is configured but "
                "HUMAN_IN_THE_LOOP is explicitly disabled (enabled=False).",
                hint=(
                    "Remove 'enabled: False' from DJGENT['HUMAN_IN_THE_LOOP'] "
                    "or remove PROTECTED_TOOLS. Protected tools require human "
                    "interaction review to be enabled."
                ),
                id="djgent.E003",
            )
        )

    return errors


@register()
def check_hitl_admin_permission(app_configs: Any, **kwargs: Any) -> List[CheckMessage]:
    """Warn when HITL is enabled but the reviewer permission may not be set up."""
    warnings: List[CheckMessage] = []

    djgent_config = getattr(settings, "DJGENT", {})
    hitl_config = djgent_config.get("HUMAN_IN_THE_LOOP", {})

    if not hitl_config:
        return warnings

    # Check if django.contrib.auth is installed (needed for permissions)
    installed_apps = getattr(settings, "INSTALLED_APPS", [])
    if "django.contrib.auth" not in installed_apps:
        warnings.append(
            Warning(
                "HUMAN_IN_THE_LOOP is configured but django.contrib.auth is not in INSTALLED_APPS.",
                hint=(
                    "Add 'django.contrib.auth' to INSTALLED_APPS to use "
                    "reviewer permission checks (djgent.can_review_human_interaction)."
                ),
                id="djgent.W002",
            )
        )

    return warnings
