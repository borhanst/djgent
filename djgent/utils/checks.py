"""System checks for djgent configuration."""

from typing import Any, Dict, List

from django.conf import settings
from django.core.checks import Error, Warning, register


@register()
def check_djgent_settings(app_configs, **kwargs) -> List[Error]:
    """
    Check if djgent settings are properly configured.

    Run with: python manage.py check
    """
    errors = []

    # Check if DJGENT setting exists
    djgent_settings = getattr(settings, "DJGENT", None)
    if not djgent_settings:
        errors.append(
            Error(
                "DJGENT setting not found in settings.py",
                hint="Add DJGENT configuration to your settings.py",
                id="djgent.E001",
            )
        )
        return errors

    # Check DEFAULT_LLM
    default_llm = djgent_settings.get("DEFAULT_LLM")
    if not default_llm:
        errors.append(
            Error(
                "DJGENT['DEFAULT_LLM'] is not set",
                hint="Set DEFAULT_LLM to a provider:model string (e.g., 'google:gemini-2.5-flash')",
                id="djgent.E002",
            )
        )

    # Check API_KEYS
    api_keys = djgent_settings.get("API_KEYS", {})
    if not api_keys:
        errors.append(
            Warning(
                "DJGENT['API_KEYS'] is empty",
                hint="Add API keys for your LLM providers (GOOGLE, OPENAI, ANTHROPIC, GROQ, etc.)",
                id="djgent.W001",
            )
        )

    # Check if at least one API key is set
    active_keys = {k: v for k, v in api_keys.items() if v and v != "your-***-here"}
    if not active_keys:
        errors.append(
            Warning(
                "No API keys are configured",
                hint="Set at least one API key in DJGENT['API_KEYS']",
                id="djgent.W002",
            )
        )

    return errors


@register()
def check_djent_llm_providers(app_configs, **kwargs) -> List[Warning]:
    """
    Check if LLM providers have their API keys configured.

    Run with: python manage.py check
    """
    warnings = []

    djgent_settings = getattr(settings, "DJGENT", {})
    api_keys = djgent_settings.get("API_KEYS", {})
    default_llm = djgent_settings.get("DEFAULT_LLM", "")

    # Map providers to their API key names
    provider_key_map = {
        "google": "GOOGLE",
        "gemini": "GOOGLE",
        "openai": "OPENAI",
        "anthropic": "ANTHROPIC",
        "groq": "GROQ",
        "openrouter": "OPENROUTER",
    }

    # Check if default LLM provider has API key
    if default_llm:
        provider = default_llm.split(":")[0].lower()
        required_key = provider_key_map.get(provider)

        if required_key:
            key_value = api_keys.get(required_key, "")
            if not key_value or key_value.startswith("your-"):
                warnings.append(
                    Warning(
                        f"Default LLM provider '{provider}' may not have valid API key",
                        hint=(
                            f"Set DJGENT['API_KEYS']['{required_key}'] or "
                            f"{required_key}_API_KEY environment variable"
                        ),
                        id="djgent.W003",
                    )
                )

    return warnings


@register()
def check_djent_installed_packages(app_configs, **kwargs) -> List[Warning]:
    """
    Check if required packages are installed.

    Run with: python manage.py check
    """
    warnings = []

    # Required packages
    required_packages = {
        "langchain": "langchain",
        "langchain_core": "langchain-core",
    }

    # Optional packages and their providers
    optional_packages = {
        "langchain_openai": "OpenAI provider",
        "langchain_anthropic": "Anthropic provider",
        "langchain_google_genai": "Google Gemini provider",
        "langchain_groq": "Groq provider",
        "langchain_ollama": "Ollama provider",
        "langchain_community": "DuckDuckGo search tool",
        "httpx": "HTTP tool",
        "duckduckgo_search": "DuckDuckGo search (legacy)",
        "ddgs": "DuckDuckGo search (recommended)",
    }

    # Check required packages
    for package, display_name in required_packages.items():
        try:
            __import__(package)
        except ImportError:
            warnings.append(
                Warning(
                    f"Required package '{package}' is not installed",
                    hint=f"Install with: pip install {display_name}",
                    id="djgent.W004",
                )
            )

    # Check optional packages
    for package, provider_name in optional_packages.items():
        try:
            __import__(package)
        except ImportError:
            warnings.append(
                Warning(
                    f"Optional package '{package}' is not installed ({provider_name})",
                    hint=f"Install if you need {provider_name}: pip install {package}",
                    id="djgent.W005",
                )
            )

    return warnings


@register()
def check_djent_tools(app_configs, **kwargs) -> List[Warning]:
    """
    Check if built-in tools are registered.

    Run with: python manage.py check
    """
    warnings = []

    try:
        from djgent.tools.registry import ToolRegistry

        djgent_settings = getattr(settings, "DJGENT", {})
        expected_tools = djgent_settings.get("BUILTIN_TOOLS", ["calculator", "datetime"])
        registered_tools = ToolRegistry.list_tools()

        for tool_name in expected_tools:
            if tool_name not in registered_tools:
                warnings.append(
                    Warning(
                        f"Built-in tool '{tool_name}' is not registered",
                        hint="Make sure djgent is in INSTALLED_APPS and app is loaded",
                        id="djgent.W006",
                    )
                )
    except ImportError:
        warnings.append(
            Warning(
                "Could not import ToolRegistry",
                hint="Make sure djgent is properly installed",
                id="djgent.W007",
            )
        )

    return warnings


@register()
def check_djent_builtin_tools_config(app_configs, **kwargs) -> List[Warning]:
    """
    Check if BUILTIN_TOOLS setting contains valid tool names.

    Run with: python manage.py check
    """
    from django.conf import settings

    warnings = []

    # Available built-in tools
    available_tools = [
        "calculator",
        "datetime",
        "http",
        "search",
        "weather",
    ]

    djgent_settings = getattr(settings, "DJGENT", {})
    builtin_tools = djgent_settings.get("BUILTIN_TOOLS", ["calculator", "datetime"])

    # Check for unknown tool names
    for tool_name in builtin_tools:
        if tool_name not in available_tools:
            warnings.append(
                Warning(
                    f"Unknown tool '{tool_name}' in BUILTIN_TOOLS setting",
                    hint=f"Available built-in tools: {available_tools}",
                    id="djgent.W008",
                )
            )

    return warnings


@register()
def check_djent_model_query_tool_config(app_configs, **kwargs) -> List[Warning]:
    """
    Check MODEL_QUERY_TOOL configuration.

    Run with: python manage.py check
    """
    from django.conf import settings

    warnings = []

    djgent_settings = getattr(settings, "DJGENT", {})
    model_query_config = djgent_settings.get("MODEL_QUERY_TOOL", {})

    if not model_query_config.get("ENABLED", True):
        return warnings  # Tool is disabled, skip checks

    # Check for sensitive models that should be excluded
    sensitive_models = [
        "auth.Permission",
        "auth.Group",
        "sessions.Session",
        "admin.LogEntry",
        "contenttypes.ContentType",
    ]

    excluded_models = model_query_config.get("EXCLUDED_MODELS", [])

    # Warn if sensitive models are not excluded
    for sensitive_model in sensitive_models:
        if sensitive_model not in excluded_models:
            warnings.append(
                Warning(
                    f"Sensitive model '{sensitive_model}' is not in EXCLUDED_MODELS",
                    hint=(
                        f"Add '{sensitive_model}' to "
                        "DJGENT['MODEL_QUERY_TOOL']['EXCLUDED_MODELS'] for security"
                    ),
                    id="djgent.W009",
                )
            )

    # Note: Sensitive fields (password, token, secret, card info, etc.) are ALWAYS excluded
    # by default. No need to warn about EXCLUDE_FIELDS anymore.

    # Validate ALLOWED_MODELS exist
    allowed_models = model_query_config.get("ALLOWED_MODELS", [])
    if allowed_models:
        from django.apps import apps

        for model_name in allowed_models:
            try:
                app_label, model = model_name.split(".", 1)
                apps.get_model(app_label, model)
            except (ValueError, LookupError):
                warnings.append(
                    Warning(
                        f"Model '{model_name}' in ALLOWED_MODELS does not exist",
                        hint=f"Check that '{model_name}' is a valid model name",
                        id="djgent.W011",
                    )
                )

    return warnings


@register()
def check_djent_auth_tool_config(app_configs, **kwargs) -> List[Warning]:
    """
    Check Django auth tool configuration.

    Run with: python manage.py check
    """
    from django.apps import apps

    warnings = []

    # Check if required apps are installed
    required_apps = [
        "django.contrib.auth",
        "django.contrib.contenttypes",
    ]

    for app_name in required_apps:
        if not apps.is_installed(app_name):
            warnings.append(
                Warning(
                    f"Required app '{app_name}' is not installed",
                    hint=f"Add '{app_name}' to INSTALLED_APPS for django_auth tool",
                    id="djgent.W012",
                )
            )

    # Check if sessions framework is installed (for session-based auth)
    if not apps.is_installed("django.contrib.sessions"):
        warnings.append(
            Warning(
                "django.contrib.sessions is not installed",
                hint=(
                    "Add 'django.contrib.sessions' to INSTALLED_APPS for "
                    "session-based authentication"
                ),
                id="djgent.W013",
            )
        )

    return warnings


@register()
def check_djent_auth_requirements_config(app_configs, **kwargs) -> List[Warning]:
    """
    Check AUTH_REQUIREMENTS configuration.

    Run with: python manage.py check
    """
    from django.conf import settings

    warnings = []

    djgent_settings = getattr(settings, "DJGENT", {})
    auth_requirements = djgent_settings.get("AUTH_REQUIREMENTS", {})

    # Validate tool configurations
    valid_tools = ["django_model", "django_auth"]
    for tool_name, config in auth_requirements.items():
        if tool_name not in valid_tools:
            warnings.append(
                Warning(
                    f"Unknown tool '{tool_name}' in AUTH_REQUIREMENTS",
                    hint=f"Valid tools are: {valid_tools}",
                    id="djgent.W014",
                )
            )
            continue

        # Check for required keys
        require_auth = config.get("require_auth_for", [])
        allow_anonymous = config.get("allow_anonymous", [])

        # Check for overlapping actions
        overlap = set(require_auth) & set(allow_anonymous)
        if overlap:
            warnings.append(
                Warning(
                    f"Action overlap in AUTH_REQUIREMENTS['{tool_name}']: {list(overlap)}",
                    hint="Actions cannot be in both require_auth_for and allow_anonymous",
                    id="djgent.W015",
                )
            )

    return warnings


@register()
def check_djent_public_models_config(app_configs, **kwargs) -> List[Warning]:
    """
    Check PUBLIC_MODELS configuration.

    Run with: python manage.py check
    """
    from django.apps import apps

    from djgent.utils.public_models import get_public_models

    warnings = []

    # Get public models from registry and settings
    public_models = get_public_models()

    if public_models:
        # Validate each model in PUBLIC_MODELS exists
        for model_name in public_models:
            try:
                app_label, model = model_name.split(".", 1)
                apps.get_model(app_label, model)
            except (ValueError, LookupError):
                warnings.append(
                    Warning(
                        f"Model '{model_name}' in PUBLIC_MODELS does not exist",
                        hint=(
                            f"Check that '{model_name}' is a valid model name "
                            "(format: 'app_label.ModelName')"
                        ),
                        id="djgent.W016",
                    )
                )
    else:
        # Inform that no public models are configured
        warnings.append(
            Warning(
                "PUBLIC_MODELS is not configured - anonymous users cannot list "
                "or view any model schemas",
                hint=(
                    "Add models to DJGENT['PUBLIC_MODELS'] or use "
                    "@register_public_model decorator"
                ),
                id="djgent.W017",
            )
        )

    return warnings


def run_djent_checks() -> Dict[str, Any]:
    """
    Run all djgent configuration checks and return results.

    Call this function programmatically to check configuration before using djgent.

    Returns:
        Dictionary with check results:
        {
            "success": bool,
            "errors": list,
            "warnings": list,
            "config": dict,
        }

    Example:
        from djgent.utils.checks import run_djent_checks

        results = run_djent_checks()
        if not results["success"]:
            print("Configuration issues:", results["errors"])
    """

    results = {
        "success": True,
        "errors": [],
        "warnings": [],
        "config": {},
    }

    # Get djgent settings
    djgent_settings = getattr(settings, "DJGENT", {})
    model_query_config = djgent_settings.get("MODEL_QUERY_TOOL", {})
    auth_requirements = djgent_settings.get("AUTH_REQUIREMENTS", {})
    from djgent.utils.public_models import get_public_models

    public_models = get_public_models()
    results["config"] = {
        "DEFAULT_LLM": djgent_settings.get("DEFAULT_LLM", "Not set"),
        "API_KEYS_CONFIGURED": bool(djgent_settings.get("API_KEYS", {})),
        "BUILTIN_TOOLS": djgent_settings.get("BUILTIN_TOOLS", []),
        "AUTO_DISCOVER_TOOLS": djgent_settings.get("AUTO_DISCOVER_TOOLS", True),
        "MODEL_QUERY_TOOL_ENABLED": model_query_config.get("ENABLED", True),
        "MODEL_QUERY_TOOL_EXCLUDED_MODELS": model_query_config.get("EXCLUDED_MODELS", []),
        "DJANGO_AUTH_TOOL_AVAILABLE": True,  # Always available
        "AUTH_REQUIREMENTS_CONFIGURED": bool(auth_requirements),
        "PUBLIC_MODELS": (
            public_models
            if public_models
            else "Not configured (anonymous users cannot access models)"
        ),
    }

    # Check if DJGENT setting exists
    if not djgent_settings:
        results["errors"].append("DJGENT setting not found in settings.py")
        results["success"] = False
        return results

    # Check DEFAULT_LLM
    if not djgent_settings.get("DEFAULT_LLM"):
        results["errors"].append("DEFAULT_LLM is not configured")
        results["success"] = False

    # Check API keys
    api_keys = djgent_settings.get("API_KEYS", {})
    active_keys = {k: v for k, v in api_keys.items() if v and not v.startswith("your-")}

    if not active_keys:
        results["warnings"].append("No API keys are configured")

    # Check BUILTIN_TOOLS configuration
    available_tools = ["calculator", "datetime", "http", "search", "weather"]
    builtin_tools = djgent_settings.get("BUILTIN_TOOLS", ["calculator", "datetime"])

    for tool_name in builtin_tools:
        if tool_name not in available_tools:
            results["warnings"].append(
                f"Unknown tool '{tool_name}' in BUILTIN_TOOLS. Available: {available_tools}"
            )

    # Check required packages
    required_packages = ["langchain", "langchain_core"]
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            results["errors"].append(f"Required package '{package}' is not installed")
            results["success"] = False

    # Check optional packages
    optional_packages = {
        "langchain_openai": "OpenAI",
        "langchain_anthropic": "Anthropic",
        "langchain_google_genai": "Google",
        "langchain_groq": "Groq",
        "langchain_community": "Search tool",
        "httpx": "HTTP tool",
    }

    missing_optional = []
    for package, feature in optional_packages.items():
        try:
            __import__(package)
        except ImportError:
            missing_optional.append(f"{package} ({feature})")

    if missing_optional:
        results["warnings"].append(
            f"Optional packages not installed: {', '.join(missing_optional)}"
        )

    # Check tools registration
    try:
        from djgent.tools.registry import ToolRegistry

        registered_tools = ToolRegistry.list_tools()
        results["config"]["REGISTERED_TOOLS"] = registered_tools

        if not registered_tools:
            results["warnings"].append("No tools are registered")
    except Exception as e:
        results["warnings"].append(f"Could not check tools: {str(e)}")

    # Check LLM provider
    default_llm = djgent_settings.get("DEFAULT_LLM", "")
    if default_llm:
        provider = default_llm.split(":")[0].lower()
        provider_key_map = {
            "google": "GOOGLE",
            "openai": "OPENAI",
            "anthropic": "ANTHROPIC",
            "groq": "GROQ",
            "openrouter": "OPENROUTER",
        }

        required_key = provider_key_map.get(provider)
        if required_key:
            key_value = api_keys.get(required_key, "")
            if not key_value or key_value.startswith("your-"):
                results["warnings"].append(
                    f"Default LLM provider '{provider}' may not have valid API key"
                )

    return results


def print_djent_checks() -> bool:
    """
    Run and print djgent configuration checks.

    Returns:
        True if all checks pass, False otherwise

    Example:
        from djgent.utils.checks import print_djent_checks

        if print_djent_checks():
            print("✅ All checks passed!")
        else:
            print("❌ Some checks failed")
    """
    results = run_djent_checks()

    print("\n" + "=" * 60)
    print("DJGENT CONFIGURATION CHECK")
    print("=" * 60)

    # Configuration
    print("\n📋 CONFIGURATION:")
    for key, value in results["config"].items():
        print(f"   • {key}: {value}")

    # Errors
    if results["errors"]:
        print("\n❌ ERRORS:")
        for error in results["errors"]:
            print(f"   • {error}")
    else:
        print("\n✅ No errors")

    # Warnings
    if results["warnings"]:
        print("\n⚠️  WARNINGS:")
        for warning in results["warnings"]:
            print(f"   • {warning}")
    else:
        print("\n✅ No warnings")

    # Summary
    print("\n" + "=" * 60)
    if results["success"] and not results["warnings"]:
        print("✅ ALL CHECKS PASSED!")
    elif results["success"]:
        print("⚠️  CHECKS PASSED WITH WARNINGS")
    else:
        print("❌ CHECKS FAILED - Please fix the errors above")
    print("=" * 60 + "\n")

    return results["success"]
