"""LLM provider management."""

from typing import Any, Callable, Dict

from djgent.exceptions import LLMError
from djgent.llm.config import LLMConfig


class _ProviderRegistry:
    """Internal registry for LLM providers."""

    _providers: Dict[str, Callable[[LLMConfig], Any]] = {}

    @classmethod
    def register(cls, name: str) -> Callable:
        """Decorator to register an LLM provider."""

        def decorator(func: Callable[[LLMConfig], Any]) -> Callable:
            cls._providers[name] = func
            return func

        return decorator

    @classmethod
    def get(cls, name: str) -> Callable[[LLMConfig], Any]:
        """Get a provider by name."""
        if name not in cls._providers:
            raise LLMError(
                f"LLM provider '{name}' not found. Available: {list(cls._providers.keys())}"
            )
        return cls._providers[name]


def register_provider(name: str) -> Callable:
    """
    Decorator to register a custom LLM provider.

    Args:
        name: Provider name

    Returns:
        The decorator

    Example:
        @register_provider("custom")
        def get_custom_llm(config: LLMConfig):
            return CustomLLM(**config.to_kwargs())
    """
    return _ProviderRegistry.register(name)


def get_llm(provider_string: str, **kwargs: Any) -> Any:
    """
    Get an LLM instance from a provider string.

    Args:
        provider_string: Format "provider:model" or just "provider"
        **kwargs: Additional configuration overrides

    Returns:
        LangChain LLM instance

    Example:
        llm = get_llm("openai:gpt-4")
        llm = get_llm("anthropic:claude-3-sonnet", temperature=0.5)
    """
    from django.conf import settings

    # Parse provider string
    if ":" in provider_string:
        provider, model = provider_string.split(":", 1)
    else:
        provider = provider_string
        model = None

    provider = provider.lower()

    # Get API keys from Django settings
    djgent_settings = getattr(settings, "DJGENT", {})
    api_keys = djgent_settings.get("API_KEYS", {})

    # Create config
    config_kwargs = {
        "provider": provider,
        "model": model or _get_default_model(provider),
        "api_key": api_keys.get(provider.upper()),
    }
    config_kwargs.update(kwargs)

    config = LLMConfig(**config_kwargs)

    # Get provider function
    provider_func = _ProviderRegistry.get(provider)

    return provider_func(config)


def _get_default_model(provider: str) -> str:
    """Get default model for a provider."""
    defaults = {
        "openai": "gpt-4o-mini",
        "anthropic": "claude-3-5-sonnet-20241022",
        "google": "gemini-2.5-flash",
        "gemini": "gemini-2.5-flash",
        "ollama": "llama3.2",
        "azure_openai": "gpt-4o-mini",
        "groq": "llama-3.3-70b-versatile",
        "openrouter": "meta-llama/llama-3.2-3b-instruct",
    }
    return defaults.get(provider, "gpt-4o-mini")


# Register built-in providers
@register_provider("openai")
def _get_openai(config: LLMConfig) -> Any:
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(**config.to_kwargs())


@register_provider("anthropic")
def _get_anthropic(config: LLMConfig) -> Any:
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(**config.to_kwargs())


@register_provider("google")
@register_provider("gemini")
def _get_google(config: LLMConfig) -> Any:
    from langchain_google_genai import ChatGoogleGenerativeAI

    kwargs = config.to_kwargs()

    return ChatGoogleGenerativeAI(**kwargs)


@register_provider("ollama")
def _get_ollama(config: LLMConfig) -> Any:
    from langchain_ollama import ChatOllama

    # Ollama doesn't need API key
    kwargs = config.to_kwargs()
    kwargs.pop("api_key", None)
    if config.base_url:
        kwargs["base_url"] = config.base_url
    else:
        kwargs["base_url"] = "http://localhost:11434"

    return ChatOllama(**kwargs)


@register_provider("azure_openai")
def _get_azure_openai(config: LLMConfig) -> Any:
    from langchain_openai import AzureChatOpenAI

    kwargs = config.to_kwargs()
    # Azure-specific configuration
    if config.base_url:
        kwargs["azure_endpoint"] = config.base_url

    return AzureChatOpenAI(**kwargs)


@register_provider("groq")
def _get_groq(config: LLMConfig) -> Any:
    from langchain_groq import ChatGroq

    kwargs = config.to_kwargs()

    return ChatGroq(**kwargs)


@register_provider("openrouter")
def _get_openrouter(config: LLMConfig) -> Any:
    from langchain_openai import ChatOpenAI

    # OpenRouter uses OpenAI-compatible API
    kwargs = config.to_kwargs()
    kwargs["base_url"] = "https://openrouter.ai/api/v1"

    # Use OPENROUTER_API_KEY if not explicitly set
    if not kwargs.get("api_key"):
        from django.conf import settings

        djgent_settings = getattr(settings, "DJGENT", {})
        api_keys = djgent_settings.get("API_KEYS", {})
        kwargs["api_key"] = api_keys.get("OPENROUTER", api_keys.get("OPENAI"))

    return ChatOpenAI(**kwargs)
