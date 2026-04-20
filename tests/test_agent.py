"""Tests for the Agent class."""

from __future__ import annotations

from unittest.mock import MagicMock, patch, AsyncMock

import pytest
from langchain_core.messages import HumanMessage, AIMessage

from djgent.agents.base import Agent


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
