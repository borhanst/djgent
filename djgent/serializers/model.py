"""Helpers for schema-driven model serialization."""

from __future__ import annotations

import types
from typing import Any, Dict, List, Optional, get_args, get_origin

from djgent.utils.model_introspection import ALWAYS_EXCLUDE_FIELDS, _is_sensitive_field


def is_pydantic_model_class(schema_class: Any) -> bool:
    """Return True when the value is a Pydantic BaseModel subclass."""
    try:
        from pydantic import BaseModel
    except ImportError:
        return False

    return isinstance(schema_class, type) and issubclass(schema_class, BaseModel)


def serialize_with_pydantic_schema(
    obj: Any,
    schema_class: Any,
    *,
    fields: Optional[List[str]] = None,
    exclude_fields: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Serialize an object using a Pydantic schema and `from_attributes`."""
    if not is_pydantic_model_class(schema_class):
        raise TypeError("schema must be a Pydantic BaseModel subclass")

    include = _build_include_map(
        schema_class,
        fields=fields,
        exclude_fields=exclude_fields,
    )
    schema = schema_class.model_validate(obj, from_attributes=True)
    return schema.model_dump(mode="json", include=include)


def _build_include_map(
    schema_class: Any,
    *,
    fields: Optional[List[str]] = None,
    exclude_fields: Optional[List[str]] = None,
) -> Dict[str, Any]:
    schema_fields = _get_model_fields(schema_class)
    excluded = set(ALWAYS_EXCLUDE_FIELDS) | set(exclude_fields or [])

    include: Dict[str, Any] = {}
    for field_name, field_info in schema_fields.items():
        if fields is not None and field_name not in fields:
            continue
        if field_name in excluded or _is_sensitive_field(field_name):
            continue

        nested_schema = _extract_nested_schema(field_info.annotation)
        if nested_schema is None:
            include[field_name] = True
            continue

        nested_include = _build_include_map(
            nested_schema,
            exclude_fields=exclude_fields,
        )
        if _is_collection_annotation(field_info.annotation):
            include[field_name] = {"__all__": nested_include}
        else:
            include[field_name] = nested_include

    return include


def _get_model_fields(schema_class: Any) -> Dict[str, Any]:
    if hasattr(schema_class, "model_fields"):
        return schema_class.model_fields
    return getattr(schema_class, "__fields__", {})


def _extract_nested_schema(annotation: Any) -> Optional[Any]:
    if annotation is None:
        return None

    if is_pydantic_model_class(annotation):
        return annotation

    origin = get_origin(annotation)
    if origin in (list, List, set, tuple):
        for arg in get_args(annotation):
            nested = _extract_nested_schema(arg)
            if nested is not None:
                return nested
        return None

    if origin in (types.UnionType, getattr(__import__("typing"), "Union")):
        for arg in get_args(annotation):
            if arg is type(None):
                continue
            nested = _extract_nested_schema(arg)
            if nested is not None:
                return nested

    return None


def _is_collection_annotation(annotation: Any) -> bool:
    origin = get_origin(annotation)
    return origin in (list, List, set, tuple)
