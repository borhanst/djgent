"""Tests for memory backends."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import HumanMessage, AIMessage

from djgent.memory.base import BaseMemory
from djgent.memory.backends import InMemoryMemory, DatabaseMemory
from djgent.memory.store import memory_store


class TestInMemoryMemory:
    """Test cases for InMemoryMemory."""

    def test_initialization(self) -> None:
        """Test InMemoryMemory initializes correctly."""
        backend = InMemoryMemory(agent_name="test", conversation_id="test-conv")
        
        assert backend.agent_name == "test"
        assert backend.conversation_id == "test-conv"
        assert backend._messages == []

    def test_add_message(self) -> None:
        """Test adding messages to memory."""
        backend = InMemoryMemory(agent_name="test", conversation_id="test-conv")
        
        backend.add_message(role="human", content="Hello")
        
        assert len(backend._messages) == 1
        assert backend._messages[0]["role"] == "human"
        assert backend._messages[0]["content"] == "Hello"

    def test_get_messages(self) -> None:
        """Test retrieving messages from memory."""
        backend = InMemoryMemory(agent_name="test", conversation_id="test-conv")
        
        backend.add_message(role="human", content="Hello")
        backend.add_message(role="ai", content="Hi there")
        
        messages = backend.get_messages()
        
        assert len(messages) == 2
        assert messages[0]["content"] == "Hello"
        assert messages[1]["content"] == "Hi there"

    def test_clear_messages(self) -> None:
        """Test clearing messages from memory."""
        backend = InMemoryMemory(agent_name="test", conversation_id="test-conv")
        backend.add_message(role="human", content="Hello")
        
        backend.clear()
        
        assert len(backend._messages) == 0

    def test_get_messages_count(self) -> None:
        """Test getting message count."""
        backend = InMemoryMemory(agent_name="test", conversation_id="test-conv")
        backend.add_message(role="human", content="Hello")
        backend.add_message(role="ai", content="Hi")
        
        count = len(backend._messages)
        
        assert count == 2


@pytest.mark.django_db
class TestDatabaseMemory:
    """Test cases for DatabaseMemory."""

    def test_initialization_without_conversation_id(self) -> None:
        """Test DatabaseMemory initializes correctly without conversation_id (creates new)."""
        backend = DatabaseMemory(agent_name="test")
        backend.initialize()
        
        assert backend.agent_name == "test"
        assert backend.conversation_id is not None

    def test_add_message(self) -> None:
        """Test adding messages to database."""
        backend = DatabaseMemory(agent_name="test")
        backend.initialize()
        
        backend.add_message(role="human", content="Hello")
        
        messages = backend.get_messages()
        assert len(messages) == 1


class TestMemoryStore:
    """Test cases for MemoryStore."""

    def test_store_exists(self) -> None:
        """Test memory store exists."""
        store = memory_store
        
        assert store is not None

    def test_get_memory_backend(self) -> None:
        """Test getting memory backend."""
        from djgent.memory import get_memory_backend
        backend = get_memory_backend("memory", agent_name="test")
        
        assert isinstance(backend, InMemoryMemory)
