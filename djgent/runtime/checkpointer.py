"""Helpers for configuring LangGraph checkpointers from Django settings."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import quote

from django.conf import settings

from djgent.exceptions import ConfigurationError
from djgent.utils.helpers import merge_settings

_CHECKPOINTER_CACHE: Dict[tuple[Any, ...], Any] = {}


def resolve_checkpointer(explicit_checkpointer: Optional[Any] = None) -> Optional[Any]:
    """Resolve the LangGraph checkpointer for an agent."""
    if explicit_checkpointer is False:
        return None
    if explicit_checkpointer is not None:
        return explicit_checkpointer

    configured = merge_settings().get("CHECKPOINTER", "auto")
    if configured in (None, False):
        return None
    if configured != "auto":
        return configured

    database_config = settings.DATABASES.get("default", {})
    engine = database_config.get("ENGINE", "")
    if "postgresql" in engine or "postgres" in engine:
        return _build_postgres_checkpointer(database_config)
    return _build_sqlite_checkpointer(database_config)


def _build_postgres_checkpointer(database_config: Dict[str, Any]) -> Any:
    """Build and cache a Postgres-backed LangGraph checkpointer."""
    uri = _postgres_connection_uri(database_config)
    cache_key = ("postgres", uri)
    if cache_key not in _CHECKPOINTER_CACHE:
        try:
            import psycopg
            from langgraph.checkpoint.postgres import PostgresSaver
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise ConfigurationError(
                "Postgres checkpointer support requires "
                "'langgraph-checkpoint-postgres'."
            ) from exc

        connection = psycopg.connect(uri, autocommit=True, row_factory=dict_row)
        checkpointer = PostgresSaver(connection)
        checkpointer.setup()
        _CHECKPOINTER_CACHE[cache_key] = checkpointer
    return _CHECKPOINTER_CACHE[cache_key]


def _build_sqlite_checkpointer(database_config: Dict[str, Any]) -> Any:
    """Build and cache a SQLite-backed LangGraph checkpointer."""
    path = _sqlite_checkpointer_path(database_config)
    cache_key = ("sqlite", str(path))
    if cache_key not in _CHECKPOINTER_CACHE:
        try:
            from langgraph.checkpoint.sqlite import SqliteSaver
        except ImportError as exc:
            raise ConfigurationError(
                "SQLite checkpointer support requires 'langgraph-checkpoint-sqlite'."
            ) from exc

        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path, check_same_thread=False)
        _CHECKPOINTER_CACHE[cache_key] = SqliteSaver(connection)
    return _CHECKPOINTER_CACHE[cache_key]


def _postgres_connection_uri(database_config: Dict[str, Any]) -> str:
    """Build a libpq connection URI from Django's default database settings."""
    name = quote(str(database_config.get("NAME") or ""), safe="")
    user = quote(str(database_config.get("USER") or ""), safe="")
    password = quote(str(database_config.get("PASSWORD") or ""), safe="")
    host = database_config.get("HOST") or "localhost"
    port = database_config.get("PORT") or "5432"

    credentials = user
    if password:
        credentials = f"{credentials}:{password}"
    if credentials:
        credentials = f"{credentials}@"

    return f"postgresql://{credentials}{host}:{port}/{name}"


def _sqlite_checkpointer_path(database_config: Dict[str, Any]) -> Path:
    """Resolve the dedicated SQLite checkpoint database path."""
    base_dir = getattr(settings, "BASE_DIR", None)
    if base_dir:
        return Path(base_dir) / "djgent_checkpoints.sqlite3"

    database_name = database_config.get("NAME")
    if database_name and database_name != ":memory:":
        return Path(database_name).expanduser().resolve().parent / "djgent_checkpoints.sqlite3"

    return Path.cwd() / "djgent_checkpoints.sqlite3"
