"""Memory backend implementations for djgent."""

from datetime import timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.utils import timezone

from djgent.memory.base import BaseMemory


class InMemoryMemory(BaseMemory):
    """
    In-memory storage for conversation history.

    Messages are stored in memory and lost when the process ends.
    Useful for testing or temporary conversations.
    """

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._messages: List[Dict[str, Any]] = []
        self._states: Dict[str, Dict[str, Any]] = {}
        self._created_at = timezone.now()
        self._updated_at = self._created_at

    def initialize(self) -> None:
        """Initialize in-memory storage."""
        self._initialized = True

    def add_message(self, role: str, content: str, **metadata: Any) -> None:
        """Add a message to memory."""
        self._messages.append({
            'role': role,
            'content': content,
            'created_at': timezone.now(),
            'metadata': metadata,
        })
        self._updated_at = timezone.now()

    def get_messages(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get messages from memory."""
        if limit:
            return self._messages[-limit:]
        return list(self._messages)

    def get_messages_as_langchain(self, limit: Optional[int] = None) -> List[Any]:
        """Get messages as LangChain message objects."""
        from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

        messages = []
        source = self.get_messages(limit) if limit else self._messages

        for msg in source:
            role = msg['role']
            content = msg['content']

            if role == 'human':
                messages.append(HumanMessage(content=content))
            elif role == 'ai':
                messages.append(AIMessage(content=content))
            elif role == 'system':
                messages.append(SystemMessage(content=content))

        return messages

    def clear(self) -> None:
        """Clear all messages."""
        self._messages.clear()
        self._updated_at = timezone.now()

    def get_conversation_info(self) -> Dict[str, Any]:
        """Get conversation metadata."""
        return {
            'id': 'memory',
            'agent_name': self.agent_name,
            'user': self.user.username if self.user else None,
            'created_at': self._created_at,
            'updated_at': self._updated_at,
            'message_count': len(self._messages),
            'backend': 'memory',
        }

    def get_state(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Return runtime state for a thread."""
        return self._states.get(thread_id)

    def save_state(self, thread_id: str, state: Dict[str, Any]) -> None:
        """Persist runtime state for a thread."""
        self._states[thread_id] = state
        self._updated_at = timezone.now()

    def clear_state(self, thread_id: str) -> None:
        """Clear runtime state for a thread."""
        self._states.pop(thread_id, None)
        self._updated_at = timezone.now()


class DatabaseMemory(BaseMemory):
    """
    Database-backed storage for conversation history.

    Messages are stored in Django models and persist across sessions.
    """

    def __init__(
        self,
        *args: Any,
        name: Optional[str] = None,
        conversation_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ):
        super().__init__(*args, **kwargs)
        self.conversation_name = conversation_name or name or ""
        self.conversation_metadata = metadata or {}
        self._conversation = None

    def initialize(self) -> None:
        """Initialize or load conversation from database."""
        from djgent.models import Conversation

        if self.conversation_id:
            # Load existing conversation
            self._conversation = Conversation.objects.get(
                id=self.conversation_id,
                agent_name=self.agent_name,
            )
        else:
            # Create new conversation
            self._conversation = Conversation.objects.create(
                agent_name=self.agent_name,
                name=self.conversation_name,
                user=self.user,
                metadata=self.conversation_metadata,
            )
            self.conversation_id = str(self._conversation.id)

        self._initialized = True

    @property
    def conversation(self):
        """Get the conversation object, initializing if needed."""
        if not self._initialized:
            self.initialize()
        return self._conversation

    def add_message(self, role: str, content: str, **metadata: Any) -> None:
        """Add a message to the database."""
        from djgent.models import Message

        if not self._initialized:
            self.initialize()

        input_tokens = int(metadata.pop("input_tokens", 0) or 0)
        output_tokens = int(metadata.pop("output_tokens", 0) or 0)
        total_tokens = int(
            metadata.pop("total_tokens", 0) or (input_tokens + output_tokens)
        )
        estimated_cost = Decimal(str(metadata.pop("estimated_cost", "0") or "0"))

        Message.objects.create(
            conversation=self._conversation,
            role=role,
            content=content,
            metadata=metadata,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_cost=estimated_cost,
        )

        if role == "ai":
            self._conversation.add_usage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                estimated_cost=estimated_cost,
            )
        else:
            self._conversation.touch()

    def get_messages(self, limit: Optional[int] = None) -> List[Any]:
        """Get messages from the database."""
        from djgent.models import Message

        if not self._initialized:
            self.initialize()

        queryset = Message.objects.filter(conversation=self._conversation)
        if limit:
            queryset = queryset[:limit]
        return list(queryset)

    def get_messages_as_langchain(self, limit: Optional[int] = None) -> List[Any]:
        """Get messages as LangChain message objects."""
        messages = self.get_messages(limit)
        return [msg.to_langchain_message() for msg in messages]

    def clear(self) -> None:
        """Clear all messages in the conversation."""
        from djgent.models import Message

        if not self._initialized:
            self.initialize()

        Message.objects.filter(conversation=self._conversation).delete()
        self._conversation.input_tokens = 0
        self._conversation.output_tokens = 0
        self._conversation.total_tokens = 0
        self._conversation.estimated_cost = Decimal("0")
        self._conversation.updated_at = timezone.now()
        self._conversation.save(
            update_fields=[
                "input_tokens",
                "output_tokens",
                "total_tokens",
                "estimated_cost",
                "updated_at",
            ]
        )

    def get_conversation_info(self) -> Dict[str, Any]:
        """Get conversation metadata."""
        if not self._initialized:
            self.initialize()

        return {
            'id': str(self._conversation.id),
            'agent_name': self._conversation.agent_name,
            'name': self._conversation.name,
            'user': self._conversation.user.username if self._conversation.user else None,
            'created_at': self._conversation.created_at,
            'updated_at': self._conversation.updated_at,
            'message_count': self._conversation.message_count,
            'input_tokens': self._conversation.input_tokens,
            'output_tokens': self._conversation.output_tokens,
            'total_tokens': self._conversation.total_tokens,
            'estimated_cost': str(self._conversation.estimated_cost),
            'metadata': self._conversation.metadata,
            'backend': 'database',
        }

    def delete(self) -> None:
        """Delete the entire conversation."""
        if self._conversation:
            self._conversation.delete()
            self._conversation = None
            self._initialized = False

    def get_state(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Return runtime state for a thread."""
        if not self._initialized:
            self.initialize()
        return self._conversation.get_runtime_state(thread_id)

    def save_state(self, thread_id: str, state: Dict[str, Any]) -> None:
        """Persist runtime state for a thread."""
        if not self._initialized:
            self.initialize()
        self._conversation.set_runtime_state(thread_id, state)

    def clear_state(self, thread_id: str) -> None:
        """Clear runtime state for a thread."""
        if not self._initialized:
            self.initialize()
        metadata = dict(self._conversation.metadata or {})
        runtime_state = dict(metadata.get("runtime_state", {}))
        runtime_state.pop(thread_id, None)
        metadata["runtime_state"] = runtime_state
        self._conversation.metadata = metadata
        self._conversation.save(update_fields=["metadata", "updated_at"])


def get_memory_backend(
    backend: str = "database",
    **kwargs: Any,
) -> BaseMemory:
    """
    Get a memory backend by name.

    Args:
        backend: Backend name ('database', 'memory')
        **kwargs: Arguments passed to the backend constructor

    Returns:
        Memory backend instance

    Example:
        memory = get_memory_backend("database", agent_name="assistant")
        memory = get_memory_backend("memory", agent_name="test-bot")
    """
    backends = {
        "database": DatabaseMemory,
        "db": DatabaseMemory,
        "memory": InMemoryMemory,
        "in_memory": InMemoryMemory,
    }

    backend_class = backends.get(backend.lower(), InMemoryMemory)
    return backend_class(**kwargs)
