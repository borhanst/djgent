"""Tests for the Agent class."""

from __future__ import annotations

from unittest.mock import MagicMock, patch, AsyncMock

import pytest
from langchain_core.messages import HumanMessage, AIMessage

from djgent.agents.base import Agent
from djgent.memory.backends import DatabaseMemory, InMemoryMemory


@pytest.mark.django_db
class TestAgent:
    """Test cases for the Agent class."""

    def test_agent_initialization(self, agent_kwargs: dict, mock_llm: MagicMock) -> None:
        """Test agent initializes with correct attributes."""
        agent = Agent(llm=mock_llm, **agent_kwargs)
        
        assert agent.name == "test_agent"
        assert agent.llm == mock_llm
        assert agent.memory is False
        assert agent.system_prompt == "You are a helpful assistant."

    def test_agent_initialization_with_memory(
        self, 
        agent_kwargs: dict, 
        mock_llm: MagicMock
    ) -> None:
        """Test agent initializes with memory enabled."""
        agent_kwargs["memory"] = True
        agent = Agent(llm=mock_llm, **agent_kwargs)
        
        assert agent.memory is True

    def test_agent_name_required(self) -> None:
        """Test that agent name is required."""
        with pytest.raises(TypeError):
            Agent()

    def test_agent_run_returns_response(
        self, 
        agent_kwargs: dict, 
        mock_llm: MagicMock
    ) -> None:
        """Test agent run method returns a response."""
        agent = Agent(llm=mock_llm, **agent_kwargs)
        
        response = agent.run("Hello")
        
        assert response is not None
        assert isinstance(response, str)

    def test_agent_with_tools(
        self, 
        agent_kwargs: dict, 
        mock_llm: MagicMock
    ) -> None:
        """Test agent with tools."""
        agent_kwargs["tools"] = ["calculator"]
        agent = Agent(llm=mock_llm, **agent_kwargs)
        
        assert len(agent.tools) > 0

    def test_create_uses_settings_memory_backend_by_default(
        self, settings, mock_llm: MagicMock
    ) -> None:
        """Test Agent.create uses DJGENT MEMORY_BACKEND when omitted."""
        settings.DJGENT = {
            "DEFAULT_LLM": "openai:gpt-4o-mini",
            "MEMORY_BACKEND": "database",
        }

        with patch("djgent.agents.base.get_llm", return_value=mock_llm):
            agent = Agent.create(name="settings-memory")

        assert agent.memory is True
        assert agent.memory_backend_type == "database"
        assert isinstance(agent._memory_backend, DatabaseMemory)

    def test_create_memory_backend_argument_overrides_settings(
        self, settings, mock_llm: MagicMock
    ) -> None:
        """Test explicit memory_backend wins over DJGENT MEMORY_BACKEND."""
        settings.DJGENT = {
            "DEFAULT_LLM": "openai:gpt-4o-mini",
            "MEMORY_BACKEND": "database",
        }

        with patch("djgent.agents.base.get_llm", return_value=mock_llm):
            agent = Agent.create(
                name="explicit-memory",
                memory_backend="memory",
            )

        assert agent.memory is True
        assert agent.memory_backend_type == "memory"
        assert isinstance(agent._memory_backend, InMemoryMemory)

    def test_create_uses_settings_memory_enabled_by_default(
        self, settings, mock_llm: MagicMock
    ) -> None:
        """Test Agent.create uses DJGENT MEMORY_ENABLED when omitted."""
        settings.DJGENT = {
            "DEFAULT_LLM": "openai:gpt-4o-mini",
            "MEMORY_ENABLED": False,
            "MEMORY_BACKEND": "database",
        }

        with patch("djgent.agents.base.get_llm", return_value=mock_llm):
            agent = Agent.create(name="memory-disabled")

        assert agent.memory is False
        assert agent._memory_backend is None

    def test_create_memory_argument_overrides_settings(
        self, settings, mock_llm: MagicMock
    ) -> None:
        """Test explicit memory=True wins over DJGENT MEMORY_ENABLED."""
        settings.DJGENT = {
            "DEFAULT_LLM": "openai:gpt-4o-mini",
            "MEMORY_ENABLED": False,
            "MEMORY_BACKEND": "database",
        }

        with patch("djgent.agents.base.get_llm", return_value=mock_llm):
            agent = Agent.create(name="memory-enabled", memory=True)

        assert agent.memory is True
        assert agent.memory_backend_type == "database"
        assert isinstance(agent._memory_backend, DatabaseMemory)


@pytest.mark.django_db
class TestAgentTools:
    """Test cases for agent tool handling."""

    def test_tools_list(
        self, 
        agent_kwargs: dict, 
        mock_llm: MagicMock
    ) -> None:
        """Test agent tools list."""
        agent_kwargs["tools"] = ["calculator", "datetime"]
        agent = Agent(llm=mock_llm, **agent_kwargs)
        
        assert len(agent.tools) == 2

    def test_tools_from_string(
        self, 
        agent_kwargs: dict, 
        mock_llm: MagicMock
    ) -> None:
        """Test agent loads tools from string names."""
        agent_kwargs["tools"] = ["calculator"]
        agent = Agent(llm=mock_llm, **agent_kwargs)
        
        assert agent.tools is not None
