"""Model introspection utilities for Django model discovery and schema inspection."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type

from django.apps import apps
from django.db import models
from django.db.models.fields.related import RelatedField

# Always excluded field names (sensitive data)
ALWAYS_EXCLUDE_FIELDS = [
    # Authentication
    "password",
    "passwd",
    "credentials",
    # Tokens and keys
    "token",
    "tokens",
    "api_key",
    "apikey",
    "secret_key",
    "secretkey",
    "private_key",
    "privatekey",
    "access_token",
    "refresh_token",
    "auth_token",
    "session_key",
    # Payment/Financial
    "card_number",
    "cardnumber",
    "credit_card",
    "creditcard",
    "card_cvv",
    "card_cvc",
    "card_pin",
    "bank_account",
    "bankaccount",
    "account_number",
    "routing_number",
    "ssn",
    "social_security",
    # Personal sensitive
    "passport_number",
    "drivers_license",
    "medical_record",
    # Security
    "security_question",
    "security_answer",
    "recovery_code",
    "backup_code",
]

# Field name patterns that should be excluded (substring matching)
ALWAYS_EXCLUDE_PATTERNS = [
    "password",
    "passwd",
    "token",
    "secret",
    "private_key",
    "api_key",
    "apikey",
    "card_number",
    "cardnumber",
    "cvv",
    "cvc",
    "pin",
    "ssn",
    "social_security",
]


@dataclass
class FieldInfo:
    """Information about a model field."""

    name: str
    type: str
    verbose_name: str
    help_text: str = ""
    blank: bool = False
    null: bool = False
    primary_key: bool = False
    unique: bool = False
    max_length: Optional[int] = None
    choices: Optional[List[Dict[str, Any]]] = None
    related_model: Optional[str] = None
    reverse: bool = False  # True for reverse relations


@dataclass
class ModelInfo:
    """Information about a Django model."""

    app_label: str
    model_name: str
    full_name: str  # "app_label.ModelName"
    verbose_name: str
    verbose_name_plural: str
    fields: List[FieldInfo] = field(default_factory=list)
    primary_key_field: Optional[str] = None

    def __str__(self) -> str:
        return self.full_name


def get_all_models(
    include_auto: bool = False,
    exclude_models: Optional[List[str]] = None,
    allowed_models: Optional[List[str]] = None,
) -> Dict[str, ModelInfo]:
    """
    Get all registered Django models.

    Args:
        include_auto: Include auto-created models (like ManyToMany through)
        exclude_models: List of model full names to exclude
        allowed_models: If provided, only return these models (whitelist)

    Returns:
        Dict mapping "app_label.ModelName" to ModelInfo
    """
    exclude_models = exclude_models or []
    allowed_models = allowed_models or None

    all_models = {}

    # Django 5.2+ uses 'include_auto_created' instead of 'include_auto'
    for model_class in apps.get_models():
        full_name = f"{model_class._meta.app_label}.{model_class.__name__}"

        # Skip auto-created models if not requested
        if not include_auto and model_class._meta.auto_created:
            continue

        # Check exclusions
        if full_name in exclude_models:
            continue

        # Check whitelist
        if allowed_models and full_name not in allowed_models:
            continue

        model_info = get_model_schema(model_class)
        all_models[full_name] = model_info

    return all_models


def get_model_schema(model_class: Type[models.Model]) -> ModelInfo:
    """
    Get schema information for a Django model.

    Args:
        model_class: The Django model class

    Returns:
        ModelInfo with field details
    """
    meta = model_class._meta

    fields = []
    primary_key_field = None

    # Get all concrete fields
    for f in meta.get_fields():
        field_info = _get_field_info(f)
        fields.append(field_info)

        if field_info.primary_key:
            primary_key_field = field_info.name

    # Sort fields: primary key first, then by name
    fields.sort(key=lambda f: (not f.primary_key, f.name))

    return ModelInfo(
        app_label=meta.app_label,
        model_name=meta.model_name,
        full_name=f"{meta.app_label}.{meta.model_name}",
        verbose_name=meta.verbose_name,
        verbose_name_plural=meta.verbose_name_plural,
        fields=fields,
        primary_key_field=primary_key_field,
    )


def _get_field_info(f: models.Field) -> FieldInfo:
    """Extract field information from a Django field."""
    field_type = f.__class__.__name__
    choices = None

    # Handle related fields (reverse relations don't have choices)
    if isinstance(f, (models.ManyToManyRel, models.ManyToOneRel)):
        related_model = f"{f.related_model._meta.app_label}.{f.related_model.__name__}"
        if isinstance(f, models.ManyToManyRel):
            field_type = f"ManyToMany({related_model})"
        else:
            field_type = f"ReverseFK({related_model})"
        return FieldInfo(
            name=f.name,
            type=field_type,
            verbose_name=f.name.replace("_", " ").title(),
            related_model=related_model,
            reverse=True,
        )

    # Get choices if available
    if hasattr(f, "choices") and f.choices:
        choices = [{"value": value, "label": label} for value, label in f.choices]

    # Handle related fields
    related_model = None
    if isinstance(f, RelatedField):
        related_model = f"{f.related_model._meta.app_label}.{f.related_model.__name__}"
        field_type = f"{field_type}({related_model})"

    return FieldInfo(
        name=f.name,
        type=field_type,
        verbose_name=getattr(f, "verbose_name", f.name).replace("_", " ").title(),
        help_text=getattr(f, "help_text", ""),
        blank=getattr(f, "blank", False),
        null=getattr(f, "null", False),
        primary_key=getattr(f, "primary_key", False),
        unique=getattr(f, "unique", False),
        max_length=getattr(f, "max_length", None),
        choices=choices,
        related_model=related_model,
        reverse=False,
    )


def _is_sensitive_field(field_name: str) -> bool:
    """
    Check if a field name matches sensitive patterns.

    Args:
        field_name: The field name to check

    Returns:
        True if the field appears to contain sensitive data
    """
    field_name_lower = field_name.lower()

    for pattern in ALWAYS_EXCLUDE_PATTERNS:
        if pattern in field_name_lower:
            return True

    return False


def search_models(
    query: str,
    exclude_models: Optional[List[str]] = None,
    allowed_models: Optional[List[str]] = None,
) -> List[str]:
    """
    Search for models by name or verbose name.

    Args:
        query: Search query (case-insensitive)
        exclude_models: Models to exclude
        allowed_models: Allowed models (whitelist)

    Returns:
        List of matching model full names
    """
    all_models = get_all_models(
        exclude_models=exclude_models,
        allowed_models=allowed_models,
    )

    query_lower = query.lower()
    matches = []

    for full_name, info in all_models.items():
        # Search in full name, app label, model name, verbose names
        searchable = [
            full_name,
            info.app_label,
            info.model_name,
            info.verbose_name,
            info.verbose_name_plural,
        ]

        if any(query_lower in s.lower() for s in searchable):
            matches.append(full_name)

    return sorted(matches)


def filter_model_queryset(
    model_class: Type[models.Model],
    filters: Optional[Dict[str, Any]] = None,
    search: Optional[str] = None,
    search_fields: Optional[List[str]] = None,
    order_by: Optional[List[str]] = None,
    limit: int = 100,
    offset: int = 0,
    exclude_fields: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Filter and query a model's queryset safely.

    Args:
        model_class: The Django model class
        filters: Django-style filters (e.g., {"status": "active", "created__gte": "2024-01-01"})
        search: Search term for text fields
        search_fields: Fields to search in (default: first text field)
        order_by: Fields to order by (prefix with - for descending)
        limit: Maximum results to return
        offset: Number of results to skip
        exclude_fields: Extra fields to exclude from results
            (in addition to always-excluded sensitive fields)

    Returns:
        Dict with count, total, and data (list of dicts)
    """

    filters = filters or {}

    # Always exclude sensitive fields, plus any user-specified exclusions
    base_exclude = ALWAYS_EXCLUDE_FIELDS.copy()
    if exclude_fields:
        base_exclude.extend(exclude_fields)
    exclude_fields = list(set(base_exclude))  # Remove duplicates

    # Build queryset
    qs = model_class.objects.all()

    # Apply filters
    if filters:
        qs = qs.filter(**filters)

    # Apply search
    if search:
        qs = _apply_search(qs, search, search_fields, model_class)

    # Apply ordering
    if order_by:
        qs = qs.order_by(*order_by)
    elif model_class._meta.ordering:
        qs = qs.order_by(*model_class._meta.ordering)
    else:
        # Default ordering by primary key
        pk_field = model_class._meta.pk.name
        qs = qs.order_by(pk_field)

    # Get total count before limiting
    total = qs.count()

    # Apply limit and offset
    qs = qs[offset : offset + limit]

    # Evaluate queryset and convert to dicts
    results = []
    for obj in qs:
        obj_dict = _model_to_dict(obj, exclude_fields)
        results.append(obj_dict)

    return {
        "count": len(results),
        "total": total,
        "offset": offset,
        "limit": limit,
        "data": results,
    }


def _apply_search(
    qs: models.QuerySet,
    search: str,
    search_fields: Optional[List[str]],
    model_class: Type[models.Model],
) -> models.QuerySet:
    """Apply full-text search across fields."""
    from django.db.models import Q

    if not search_fields:
        # Default: search in text-like fields
        search_fields = []
        for f in model_class._meta.get_fields():
            if isinstance(f, (models.CharField, models.TextField)) and not f.related_model:
                search_fields.append(f.name)

    if not search_fields:
        # No searchable fields, return original queryset
        return qs

    # Build Q object for OR search across fields
    q_objects = Q()
    for field_name in search_fields:
        q_objects |= Q(**{f"{field_name}__icontains": search})

    return qs.filter(q_objects)


def _model_to_dict(
    obj: models.Model,
    exclude_fields: Optional[List[str]] = None,
    fields: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Convert a model instance to a dictionary.

    Args:
        obj: Model instance
        exclude_fields: Fields to exclude (in addition to always-excluded sensitive fields)
        fields: Specific fields to include (None = all except excluded)

    Returns:
        Dictionary of field values
    """
    # Always exclude sensitive fields, plus any user-specified exclusions
    base_exclude = ALWAYS_EXCLUDE_FIELDS.copy()
    if exclude_fields:
        base_exclude.extend(exclude_fields)
    exclude_fields_set = set(base_exclude)  # Remove duplicates

    # Get all fields if not specified
    if fields is None:
        fields = [f.name for f in obj._meta.fields]

    result = {}

    for field_name in fields:
        # Skip excluded fields
        if field_name in exclude_fields_set:
            continue

        # Also check for sensitive patterns in field name
        if _is_sensitive_field(field_name):
            continue

        try:
            value = getattr(obj, field_name)

            # Handle special types
            if value is None:
                result[field_name] = None
            elif hasattr(value, "pk") and hasattr(value, "_meta"):
                # ForeignKey/Model - show string representation
                result[field_name] = str(value)
            elif hasattr(value, "isoformat"):
                # Date/datetime
                result[field_name] = value.isoformat()
            elif isinstance(value, (list, dict)):
                # JSONField
                result[field_name] = value
            else:
                result[field_name] = (
                    str(value) if not isinstance(value, (int, float, bool)) else value
                )

        except Exception:
            # Skip fields that can't be serialized
            continue

    return result


def get_model_by_name(full_name: str) -> Optional[Type[models.Model]]:
    """
    Get a model class by its full name.

    Args:
        full_name: "app_label.ModelName" format

    Returns:
        Model class or None if not found
    """
    try:
        app_label, model_name = full_name.split(".", 1)
        return apps.get_model(app_label, model_name)
    except (ValueError, LookupError):
        return None


def validate_model_access(
    full_name: str,
    allowed_models: Optional[List[str]] = None,
    excluded_models: Optional[List[str]] = None,
) -> tuple[bool, str]:
    """
    Validate if a model can be accessed.

    Args:
        full_name: "app_label.ModelName" format
        allowed_models: Whitelist of allowed models
        excluded_models: Blacklist of excluded models

    Returns:
        Tuple of (is_allowed, error_message)
    """
    model_class = get_model_by_name(full_name)

    if not model_class:
        return False, f"Model '{full_name}' not found"

    # Check whitelist
    if allowed_models and full_name not in allowed_models:
        return False, f"Model '{full_name}' is not in the allowed list"

    # Check blacklist
    if excluded_models and full_name in excluded_models:
        return False, f"Model '{full_name}' is excluded"

    return True, ""
