"""Tests for tools and registries."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import HumanMessage, AIMessage

from djgent.tools.base import Tool
from djgent.tools.decorators import register_tool, tool
from djgent.tools.registry import ToolRegistry
from djgent.retrieval.tools import RetrievalTool, KnowledgeIngestTool


@pytest.fixture
def isolated_tool_registry():
    """Temporarily isolate ToolRegistry state for auto-discovery tests."""
    original_tools = ToolRegistry._tools.copy()
    original_sources = ToolRegistry._sources.copy()
    original_discovered = ToolRegistry._discovered
    ToolRegistry.clear()
    sys.modules.pop("tests.auto_tools_app.tools", None)
    try:
        yield
    finally:
        ToolRegistry._tools = original_tools
        ToolRegistry._sources = original_sources
        ToolRegistry._discovered = original_discovered
        sys.modules.pop("tests.auto_tools_app.tools", None)


class TestTool:
    """Test cases for the Tool base class."""

    def test_tool_initialization(self) -> None:
        """Test tool initializes with correct attributes."""
        tool = TestToolImpl()
        
        assert tool.name == "test_tool"
        assert tool.description == "A test tool"
        assert tool.risk_level == "low"

    def test_tool_run(self) -> None:
        """Test tool execution."""
        tool = TestToolImpl()
        
        result = tool.run("test input")
        
        assert result == "Processed: test input"

    def test_tool_config(self) -> None:
        """Test tool configuration."""
        tool = TestToolImpl()
        config = tool.get_tool_config()
        
        assert config["name"] == "test_tool"
        assert config["risk_level"] == "low"
        assert config["requires_approval"] is False

    def test_check_authenticated(self) -> None:
        """Test authentication check."""
        tool = TestToolImpl()
        
        # Without runtime, should return False
        result = tool._check_authenticated()
        assert result is False

    def test_to_langchain(self) -> None:
        """Test conversion to LangChain tool."""
        tool = TestToolImpl()
        
        lc_tool = tool.to_langchain()
        
        assert lc_tool is not None
        assert lc_tool.name == "test_tool"


class TestToolImpl(Tool):
    """Test implementation of Tool."""
    
    name = "test_tool"
    description = "A test tool"
    risk_level = "low"
    
    def _run(self, input: str) -> str:
        return f"Processed: {input}"


class TestToolRegistry:
    """Test cases for ToolRegistry."""

    def test_registry_has_builtin_tools(self) -> None:
        """Test that registry has built-in tools."""
        tools = ToolRegistry.list_tools()
        
        # Should have built-in tools loaded
        assert len(tools) >= 4
        assert "calculator" in tools
        assert "datetime" in tools

    def test_get_tool_instance(self) -> None:
        """Test getting tool instance."""
        tool = ToolRegistry.get_tool_instance("calculator")
        
        assert tool is not None
        assert isinstance(tool, Tool)

    def test_has_tool(self) -> None:
        """Test checking if tool exists."""
        assert ToolRegistry.has_tool("calculator") is True
        assert ToolRegistry.has_tool("nonexistent") is False

    def test_example_book_tool_auto_discovered(self) -> None:
        """Test example ModelQueryTool class is auto-discovered."""
        tool = ToolRegistry.get_tool_instance("book_query")

        assert isinstance(tool, Tool)
        assert tool.name == "book_query"

    def test_auto_discover_registers_tool_subclasses(
        self, isolated_tool_registry, monkeypatch
    ) -> None:
        """Test auto-discovery registers Tool subclasses from tools.py."""
        from django.apps import apps

        monkeypatch.setattr(
            apps,
            "get_app_configs",
            lambda: [SimpleNamespace(name="tests.auto_tools_app")],
        )

        ToolRegistry.auto_discover()

        tool = ToolRegistry.get_tool_instance("auto_discovered_tool")
        assert isinstance(tool, Tool)
        assert tool.run() == "auto"
        assert ToolRegistry.get_tool_source(
            "auto_discovered_tool"
        ) == "tests.auto_tools_app.tools"

    def test_auto_discover_skips_duplicates_and_non_tools(
        self, isolated_tool_registry, monkeypatch
    ) -> None:
        """Test manual registrations win and non-tool classes are ignored."""
        from django.apps import apps

        class ManualDuplicateTool(Tool):
            name = "duplicate_tool"
            description = "Manual duplicate"

            def _run(self) -> str:
                return "manual duplicate"

        ToolRegistry.register(name="duplicate_tool")(ManualDuplicateTool)
        monkeypatch.setattr(
            apps,
            "get_app_configs",
            lambda: [SimpleNamespace(name="tests.auto_tools_app")],
        )

        ToolRegistry.auto_discover()

        duplicate = ToolRegistry.get_tool_instance("duplicate_tool")
        assert duplicate.run() == "manual duplicate"
        assert ToolRegistry.has_tool("not_a_tool") is False

    def test_auto_discover_keeps_decorated_function_tools(
        self, isolated_tool_registry, monkeypatch
    ) -> None:
        """Test @tool functions still self-register during auto-discovery."""
        from django.apps import apps

        monkeypatch.setattr(
            apps,
            "get_app_configs",
            lambda: [SimpleNamespace(name="tests.auto_tools_app")],
        )

        ToolRegistry.auto_discover()

        tool = ToolRegistry.get_tool_instance("decorated_auto_function")
        assert tool.run() == "decorated"

    def test_tool_decorator_registers_tool_class(
        self, isolated_tool_registry
    ) -> None:
        """Test @tool registers Tool subclasses."""

        @tool
        class DecoratedClassTool(Tool):
            name = "decorated_class_tool"
            description = "Decorated class tool"

            def _run(self, value: str) -> str:
                return value.upper()

        tool_instance = ToolRegistry.get_tool_instance("decorated_class_tool")
        assert isinstance(tool_instance, DecoratedClassTool)
        assert tool_instance.run("hello") == "HELLO"

    def test_tool_decorator_registers_tool_class_with_override(
        self, isolated_tool_registry
    ) -> None:
        """Test @tool can register Tool subclasses with name/description override."""

        @tool(name="tool_decorated_class", description="Override description")
        class ToolDecoratedClass(Tool):
            name = "original_name"
            description = "Original description"

            def _run(self) -> str:
                return self.description

        assert ToolDecoratedClass.description == "Override description"
        tool_instance = ToolRegistry.get_tool_instance("tool_decorated_class")
        assert isinstance(tool_instance, ToolDecoratedClass)
        assert tool_instance.run() == "Override description"

    def test_register_tool_alias_uses_tool_decorator(
        self, isolated_tool_registry
    ) -> None:
        """Test old register_tool import remains compatible."""

        @register_tool(name="legacy_decorated_function")
        def legacy_function() -> str:
            return "legacy"

        tool_instance = ToolRegistry.get_tool_instance("legacy_decorated_function")
        assert tool_instance.run() == "legacy"


class TestRetrievalTool:
    """Test cases for RetrievalTool."""

    def test_initialization(self) -> None:
        """Test RetrievalTool initializes correctly."""
        tool = RetrievalTool()
        
        assert tool.name == "knowledge_retrieval"
        assert tool.risk_level == "low"

    @pytest.mark.django_db
    def test_retrieval_run(self) -> None:
        """Test retrieval execution."""
        tool = RetrievalTool()
        
        # Without data, should return empty results
        result = tool.run(query="test")
        
        assert "query" in result
        assert "count" in result


class TestKnowledgeIngestTool:
    """Test cases for KnowledgeIngestTool."""

    def test_initialization(self) -> None:
        """Test KnowledgeIngestTool initializes correctly."""
        tool = KnowledgeIngestTool()
        
        assert tool.name == "knowledge_ingest"
        assert tool.risk_level == "medium"
        assert tool.requires_approval is True
