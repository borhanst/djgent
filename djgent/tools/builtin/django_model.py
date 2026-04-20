"""Django model query tool for querying any Django model."""

from typing import Any, Dict, List, Optional, Union

from django.conf import settings
from django.db.models import QuerySet

from djgent.tools.base import ModelQueryTool
from djgent.utils.model_introspection import (
    get_all_models,
    get_model_by_name,
    get_model_schema,
    validate_model_access,
)


class DjangoModelQueryTool(ModelQueryTool):
    """
    Query Django models dynamically.

    This tool provides a generic interface to query any Django model in the project.
    It uses the base ModelQueryTool class but adds support for multi-model queries
    by overriding get_queryset() to dynamically select the model.

    Actions:
    - list_models: List all available models (not from base class)
    - get_schema: Get model field schema (not from base class)
    - list: List objects from a model
    - query: Filter and retrieve objects from a model
    - get_by_id: Get single object by ID from a model
    - search: Full-text search across model fields
    - count: Count objects with optional filters

    Authentication:
    - list_models, get_schema: Available to anonymous users (if model is public)
    - query, get_by_id, search, list, count: Require authenticated user

    Example:
        # List all models (anonymous OK)
        tool._run(action="list_models")

        # Query data (requires authentication)
        tool._run(action="query", model="blog.Post", filters={"status": "published"})

        # Get by ID
        tool._run(action="get_by_id", model="products.Product", id=42)

        # Search
        tool._run(action="search", model="blog.Post", search="django")
    """

    name = "django_model"
    description = """
    Query Django models dynamically. Actions:
    - list_models: List available models (anonymous OK)
    - get_schema: Get model field schema (anonymous OK)
    - list: List objects from a model (requires auth)
    - query: Filter and retrieve objects (requires auth)
    - get_by_id: Get single object by ID (requires auth)
    - search: Full-text search (requires auth)
    - count: Count objects with filters (requires auth)

    Use this tool to query data from any Django model in the database.
    Anonymous users can only list models and view schemas for public models.
    """
    risk_level = "high"
    requires_approval = True
    approval_reason = "Dynamic model queries can expose database records."

    # Actions that require authentication (base class handles this)
    require_auth = True

    # Override allowed_actions to include our custom actions
    allowed_actions: List[str] = [
        "list_models",
        "get_schema",
        "list",
        "query",
        "get_by_id",
        "search",
        "count",
    ]

    # Model to query (set dynamically via _run)
    _current_model: Optional[str] = None

    def _run(
        self,
        action: str,
        model: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        id: Optional[Union[int, str]] = None,
        search: Optional[str] = None,
        limit: int = 10,
        offset: int = 0,
        fields: Optional[List[str]] = None,
        order_by: Optional[List[str]] = None,
        search_fields: Optional[List[str]] = None,
        app: Optional[str] = None,
        runtime: Optional[Any] = None,
        **kwargs: Any,
    ) -> str:
        """
        Execute the model query action.

        Args:
            action: Action to perform
            model: Model full name "app_label.ModelName" (required for most actions)
            filters: Django-style filters dict
            id: Object ID (for get_by_id)
            search: Search term (for search action)
            limit: Maximum results
            offset: Results offset
            fields: Specific fields to return
            order_by: Fields to order by
            search_fields: Fields to search
            app: App label filter (for list_models)
            runtime: ToolRuntime with Django context
            **kwargs: Additional arguments

        Returns:
            JSON-formatted string with results
        """
        # Handle custom actions that don't use base class
        if action == "list_models":
            return self._list_models(app=app, runtime=runtime)
        elif action == "get_schema":
            return self._get_schema(model=model, runtime=runtime)

        # For other actions, set the model and use base class implementation
        self._current_model = model
        return super()._run(
            action=action,
            filters=filters,
            id=id,
            search=search,
            limit=limit,
            offset=offset,
            fields=fields,
            order_by=order_by,
            search_fields=search_fields,
            runtime=runtime,
            **kwargs,
        )

    def get_queryset(
        self,
        runtime: Optional[Any] = None,
        user: Optional[Any] = None,
        **kwargs: Any,
    ) -> QuerySet:
        """
        Get queryset for the current model.

        This method dynamically selects the model based on the 'model' parameter
        passed to _run().

        Args:
            runtime: ToolRuntime with Django context
            user: Current user
            **kwargs: Additional arguments

        Returns:
            QuerySet for the specified model
        """
        if not self._current_model:
            raise ValueError(
                "Model name is required. Pass 'model' parameter (e.g., 'app_label.ModelName')."
            )

        # Get configuration
        config = self._get_config()

        # Validate model access
        is_allowed, error_msg = validate_model_access(
            self._current_model,
            allowed_models=config.get("ALLOWED_MODELS"),
            excluded_models=config.get("EXCLUDED_MODELS"),
        )
        if not is_allowed:
            raise ValueError(error_msg)

        # Get model class
        model_class = get_model_by_name(self._current_model)
        if not model_class:
            raise ValueError(f"Model '{self._current_model}' not found")

        return model_class.objects.all()

    def _list_models(
        self,
        app: Optional[str] = None,
        runtime: Optional[Any] = None,
    ) -> str:
        """List all available models."""
        config = self._get_config()

        allowed_models = config.get("ALLOWED_MODELS", None)
        excluded_models = config.get("EXCLUDED_MODELS", [])

        all_models = get_all_models(
            include_auto=False,
            exclude_models=excluded_models,
            allowed_models=allowed_models,
        )

        # Filter by app if specified
        if app:
            all_models = {
                name: info for name, info in all_models.items()
                if info.app_label == app
            }

        # Check if user is authenticated
        is_authenticated = self._check_authenticated(runtime)

        # If not authenticated, filter to only PUBLIC_MODELS
        if not is_authenticated:
            from djgent.utils.public_models import get_public_models
            public_models = get_public_models()

            if public_models:
                all_models = {
                    name: info for name, info in all_models.items()
                    if name in public_models
                }
            else:
                all_models = {}

        # Format response
        models_list = []
        for full_name, info in all_models.items():
            models_list.append({
                "name": full_name,
                "verbose_name": info.verbose_name,
                "verbose_name_plural": info.verbose_name_plural,
                "field_count": len(info.fields),
            })

        response = {
            "action": "list_models",
            "count": len(models_list),
            "app_filter": app,
            "models": models_list,
        }

        return self._success_response(**response)

    def _get_schema(
        self,
        model: Optional[str] = None,
        runtime: Optional[Any] = None,
    ) -> str:
        """Get schema for a specific model."""
        config = self._get_config()

        if not model:
            return self._error_response(
                "Model name is required for get_schema action"
            )

        # Validate access
        is_allowed, error_msg = validate_model_access(
            model,
            allowed_models=config.get("ALLOWED_MODELS"),
            excluded_models=config.get("EXCLUDED_MODELS"),
        )
        if not is_allowed:
            return self._error_response(error_msg)

        # Check if user is authenticated
        is_authenticated = self._check_authenticated(runtime)

        # If not authenticated, check PUBLIC_MODELS
        if not is_authenticated:
            from djgent.utils.public_models import get_public_models
            public_models = get_public_models()

            if public_models and model not in public_models:
                return self._error_response(
                    f"Model '{model}' is not in PUBLIC_MODELS. "
                    "Authentication required to view schema."
                )
            elif not public_models:
                return self._error_response(
                    "Authentication required to view model schema."
                )

        model_class = get_model_by_name(model)
        if not model_class:
            return self._error_response(f"Model '{model}' not found")

        schema = get_model_schema(model_class)

        # Get allowed fields for this model (for anonymous users)
        allowed_fields = None
        if not is_authenticated:
            from djgent.utils.public_models import get_public_model_fields
            allowed_fields = get_public_model_fields(model)

        # Format fields
        fields_list = []
        for field in schema.fields:
            # Filter fields for anonymous users if configured
            if not is_authenticated and allowed_fields is not None:
                if field.name not in allowed_fields:
                    continue

            field_info = {
                "name": field.name,
                "type": field.type,
                "verbose_name": field.verbose_name,
                "blank": field.blank,
                "null": field.null,
                "primary_key": field.primary_key,
                "unique": field.unique,
            }
            if field.max_length:
                field_info["max_length"] = field.max_length
            if field.help_text:
                field_info["help_text"] = field.help_text
            if field.choices:
                field_info["choices"] = field.choices
            if field.related_model:
                field_info["related_model"] = field.related_model

            fields_list.append(field_info)

        response = {
            "action": "get_schema",
            "model": schema.full_name,
            "verbose_name": schema.verbose_name,
            "verbose_name_plural": schema.verbose_name_plural,
            "primary_key_field": schema.primary_key_field,
            "fields": fields_list,
        }

        return self._success_response(**response)

    def _get_config(self) -> Dict[str, Any]:
        """Get tool configuration from Django settings."""
        djgent_settings = getattr(settings, "DJGENT", {})
        return djgent_settings.get("MODEL_QUERY_TOOL", {})

    def _query(
        self,
        queryset: QuerySet,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10,
        offset: int = 0,
        fields: Optional[List[str]] = None,
        order_by: Optional[List[str]] = None,
        runtime: Optional[Any] = None,
        **kwargs: Any,
    ) -> str:
        """
        Filter and retrieve objects.

        Overrides base class to add model access validation.
        """
        # Validate model access for the current model
        if self._current_model:
            config = self._get_config()
            is_allowed, error_msg = validate_model_access(
                self._current_model,
                allowed_models=config.get("ALLOWED_MODELS"),
                excluded_models=config.get("EXCLUDED_MODELS"),
            )
            if not is_allowed:
                return self._error_response(error_msg)

        # Get excluded fields from config
        config = self._get_config()
        exclude_fields = config.get("EXCLUDE_FIELDS", [])
        self.exclude_fields = exclude_fields

        return super()._query(
            queryset=queryset,
            filters=filters,
            limit=limit,
            offset=offset,
            fields=fields,
            order_by=order_by,
            **kwargs,
        )

    def _search(
        self,
        queryset: QuerySet,
        search: Optional[str] = None,
        limit: int = 10,
        fields: Optional[List[str]] = None,
        search_fields: Optional[List[str]] = None,
        runtime: Optional[Any] = None,
        **kwargs: Any,
    ) -> str:
        """
        Search across model fields.

        Overrides base class to add model access validation.
        """
        # Validate model access for the current model
        if self._current_model:
            config = self._get_config()
            is_allowed, error_msg = validate_model_access(
                self._current_model,
                allowed_models=config.get("ALLOWED_MODELS"),
                excluded_models=config.get("EXCLUDED_MODELS"),
            )
            if not is_allowed:
                return self._error_response(error_msg)

        # Get excluded fields from config
        config = self._get_config()
        exclude_fields = config.get("EXCLUDE_FIELDS", [])
        self.exclude_fields = exclude_fields

        return super()._search(
            queryset=queryset,
            search=search,
            limit=limit,
            fields=fields,
            search_fields=search_fields,
            **kwargs,
        )
