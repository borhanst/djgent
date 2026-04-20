"""Tests for tools and registries."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import HumanMessage, AIMessage

from djgent.tools.base import Tool
from djgent.tools.registry import ToolRegistry
from djgent.retrieval.tools import RetrievalTool, KnowledgeIngestTool


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
