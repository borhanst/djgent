"""Registry and decorator for registering public models."""

from typing import Dict, List, Optional, Type

from django.apps import apps
from django.db.models import Model


class PublicModelRegistry:
    """
    Registry for models that are publicly accessible (anonymous users).

    Models registered here will be visible to anonymous users via
    the django_model tool's list_models and get_schema actions.

    Example:
        # In your app's models.py or apps.py

        from djgent import register_public_model
        from .models import Post, Category

        # Register individual models with specific fields
        register_public_model(Post, fields=["id", "title", "content", "created_at"])
        register_public_model(Category, fields=["id", "name"])

        # Or use decorator
        @register_public_model(fields=["id", "title", "content"])
        class Post(models.Model):
            ...
    """

    # Dict mapping model_name -> list of allowed fields (None = all fields)
    _public_models: Dict[str, Optional[List[str]]] = {}
    _auto_discovered: bool = False

    @classmethod
    def register(
        cls,
        model: Optional[Type[Model]] = None,
        model_name: Optional[str] = None,
        fields: Optional[List[str]] = None,
    ) -> Optional[Type[Model]]:
        """
        Register a model as publicly accessible.

        Args:
            model: The model class to register
            model_name: Model name in 'app_label.ModelName' format (alternative to model class)
            fields: List of field names to expose. None = all fields visible.

        Returns:
            The model class (for decorator usage)

        Example:
            # Register by model class with fields
            register_public_model(Post, fields=["id", "title", "content"])

            # Register by name with fields
            register_public_model(model_name="blog.Post", fields=["id", "title"])

            # As decorator with fields
            @register_public_model(fields=["id", "title"])
            class Post(models.Model):
                ...
        """
        if model_name:
            cls._public_models[model_name] = fields
            return None
        elif model:
            full_name = f"{model._meta.app_label}.{model.__name__}"
            cls._public_models[full_name] = fields
            return model  # Return for decorator usage
        return None

    @classmethod
    def get_public_models(cls) -> List[str]:
        """
        Get list of registered public model names.

        Returns:
            List of model names in 'app_label.ModelName' format
        """
        return list(cls._public_models.keys())

    @classmethod
    def is_public(cls, model_name: str) -> bool:
        """
        Check if a model is registered as public.

        Args:
            model_name: Model name in 'app_label.ModelName' format

        Returns:
            True if model is public
        """
        return model_name in cls._public_models

    @classmethod
    def get_model_fields(cls, model_name: str) -> Optional[List[str]]:
        """
        Get allowed fields for a public model.

        Args:
            model_name: Model name in 'app_label.ModelName' format

        Returns:
            List of field names, or None if all fields are allowed
        """
        return cls._public_models.get(model_name)

    @classmethod
    def clear(cls) -> None:
        """Clear all registered public models."""
        cls._public_models.clear()
        cls._auto_discovered = False

    @classmethod
    def auto_discover(cls) -> None:
        """
        Auto-discover public model registrations from installed apps.

        Scans each installed Django app for a 'public_models.py' module
        and imports it to trigger model registration.
        """
        if cls._auto_discovered:
            return

        for app_config in apps.get_app_configs():
            try:
                module_name = f"{app_config.name}.public_models"
                __import__(module_name)
            except ImportError:
                pass  # App doesn't have public_models module

        cls._auto_discovered = True


def register_public_model(model=None, *, model_name=None, fields=None):
    """
    Decorator/function to register a model as publicly accessible.

    Anonymous users will be able to list and view schemas for
    registered models via the django_model tool.

    Args:
        model: The model class (when used as decorator)
        model_name: Model name in 'app_label.ModelName' format
        fields: List of field names to expose to anonymous users.
                None = all fields visible (except sensitive fields)

    Returns:
        The model class (for decorator) or None

    Example:
        # As decorator with fields
        @register_public_model(fields=["id", "title", "content"])
        class Post(models.Model):
            title = models.CharField(max_length=200)
            ...

        # Register existing model with fields
        register_public_model(Post, fields=["id", "title", "content"])

        # Register by name with fields
        register_public_model(model_name="blog.Post", fields=["id", "title"])

        # In apps.py ready() method
        def ready(self):
            from djgent import register_public_model
            from .models import Post
            register_public_model(Post, fields=["id", "title", "content"])
    """

    def _register(model_cls: Type[Model]) -> Type[Model]:
        PublicModelRegistry.register(model=model_cls, fields=fields)
        return model_cls

    if model is not None:
        # Used as @register_public_model without parentheses
        return _register(model)

    # Used as @register_public_model() or register_public_model(model_name="...")
    if model_name:
        PublicModelRegistry.register(model_name=model_name, fields=fields)
        return None

    return _register


def get_public_models() -> List[str]:
    """
    Get all registered public models.

    Combines models from:
    1. PublicModelRegistry (decorator registrations)
    2. DJGENT['PUBLIC_MODELS'] setting

    Returns:
        List of model names in 'app_label.ModelName' format
    """
    from django.conf import settings

    # Get from registry
    registry_models = PublicModelRegistry.get_public_models()

    # Get from settings (supports both list and dict format)
    djgent_settings = getattr(settings, "DJGENT", {})
    settings_public = djgent_settings.get("PUBLIC_MODELS", [])

    # Handle dict format: {"blog.Post": ["id", "title"], "products.Category": None}
    if isinstance(settings_public, dict):
        settings_models = list(settings_public.keys())
    else:
        settings_models = list(settings_public)

    # Combine and return unique list
    all_models = list(set(registry_models + settings_models))
    return all_models


def get_public_model_fields(model_name: str) -> Optional[List[str]]:
    """
    Get allowed fields for a public model.

    Checks both registry and settings for field configuration.
    Registry fields take precedence over settings.

    Args:
        model_name: Model name in 'app_label.ModelName' format

    Returns:
        List of field names, None if all fields allowed, or empty list if not found
    """
    from django.conf import settings

    # Check registry first (takes precedence)
    registry_fields = PublicModelRegistry.get_model_fields(model_name)
    if registry_fields is not None:
        return registry_fields

    # Check settings
    djgent_settings = getattr(settings, "DJGENT", {})
    settings_public = djgent_settings.get("PUBLIC_MODELS", [])

    # Handle dict format
    if isinstance(settings_public, dict):
        return settings_public.get(model_name)

    # List format - no field restrictions
    if model_name in settings_public:
        return None  # All fields allowed

    return []  # Not a public model
