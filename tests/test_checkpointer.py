"""Tests for automatic LangGraph checkpointer configuration."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from djgent.agents.base import Agent
from djgent.runtime import checkpointer
from djgent.runtime.checkpointer import resolve_checkpointer


def test_auto_checkpointer_uses_postgres_for_postgresql_engine(settings) -> None:
    settings.DATABASES["default"] = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "djgent",
        "USER": "djgent",
        "PASSWORD": "secret",
        "HOST": "localhost",
        "PORT": "5432",
    }
    settings.DJGENT = {"CHECKPOINTER": "auto"}
    expected = object()

    with patch(
        "djgent.runtime.checkpointer._build_postgres_checkpointer",
        return_value=expected,
    ) as build_postgres:
        assert resolve_checkpointer() is expected

    build_postgres.assert_called_once_with(settings.DATABASES["default"])


def test_postgres_checkpointer_calls_setup(monkeypatch) -> None:
    checkpointer._CHECKPOINTER_CACHE.clear()
    database_config = {
        "NAME": "djgent",
        "USER": "djgent",
        "PASSWORD": "secret",
        "HOST": "localhost",
        "PORT": "5432",
    }
    connection = object()
    saver = MagicMock()
    psycopg_module = SimpleNamespace(connect=MagicMock(return_value=connection))
    rows_module = SimpleNamespace(dict_row=object())
    postgres_module = SimpleNamespace(PostgresSaver=MagicMock(return_value=saver))
    monkeypatch.setitem(sys.modules, "psycopg", psycopg_module)
    monkeypatch.setitem(sys.modules, "psycopg.rows", rows_module)
    monkeypatch.setitem(sys.modules, "langgraph.checkpoint.postgres", postgres_module)

    assert checkpointer._build_postgres_checkpointer(database_config) is saver

    psycopg_module.connect.assert_called_once()
    postgres_module.PostgresSaver.assert_called_once_with(connection)
    saver.setup.assert_called_once_with()
    checkpointer._CHECKPOINTER_CACHE.clear()


def test_auto_checkpointer_uses_sqlite_for_sqlite_engine(settings) -> None:
    settings.DATABASES["default"] = {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
    settings.DJGENT = {"CHECKPOINTER": "auto"}
    expected = object()

    with patch(
        "djgent.runtime.checkpointer._build_sqlite_checkpointer",
        return_value=expected,
    ) as build_sqlite:
        assert resolve_checkpointer() is expected

    build_sqlite.assert_called_once_with(settings.DATABASES["default"])


def test_auto_checkpointer_falls_back_to_sqlite_for_non_postgres_engine(settings) -> None:
    settings.DATABASES["default"] = {
        "ENGINE": "django.db.backends.mysql",
        "NAME": "djgent",
    }
    settings.DJGENT = {"CHECKPOINTER": "auto"}
    expected = object()

    with patch(
        "djgent.runtime.checkpointer._build_sqlite_checkpointer",
        return_value=expected,
    ) as build_sqlite:
        assert resolve_checkpointer() is expected

    build_sqlite.assert_called_once_with(settings.DATABASES["default"])


def test_create_explicit_checkpointer_overrides_settings(settings, mock_llm: MagicMock) -> None:
    settings.DJGENT = {
        "DEFAULT_LLM": "openai:gpt-4o-mini",
        "CHECKPOINTER": "auto",
    }
    explicit_checkpointer = object()

    with (
        patch("djgent.agents.base.get_llm", return_value=mock_llm),
        patch(
            "djgent.agents.base.resolve_checkpointer",
            return_value=explicit_checkpointer,
        ) as resolve,
    ):
        agent = Agent.create(name="explicit-checkpointer", checkpointer=explicit_checkpointer)
        _, resolved_checkpointer = agent._build_langchain_runtime()

    assert agent._langchain_checkpointer is explicit_checkpointer
    assert resolved_checkpointer is explicit_checkpointer
    resolve.assert_called_once_with(explicit_checkpointer)


def test_settings_none_disables_auto_checkpointer(settings) -> None:
    settings.DJGENT = {"CHECKPOINTER": None}

    assert resolve_checkpointer() is None


def test_explicit_false_disables_checkpointer(settings) -> None:
    settings.DJGENT = {"CHECKPOINTER": "auto"}

    assert resolve_checkpointer(False) is None


def test_langchain_middleware_checkpointer_is_not_used(settings) -> None:
    middleware_checkpointer = object()
    settings.DJGENT = {
        "CHECKPOINTER": None,
        "LANGCHAIN_MIDDLEWARE": {"checkpointer": middleware_checkpointer},
    }

    assert resolve_checkpointer() is None
