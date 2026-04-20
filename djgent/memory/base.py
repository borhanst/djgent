"""Base memory backend for djgent."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BaseMemory(ABC):
    """
    Abstract base class for memory backends.

    Memory backends store conversation history for agents.
    """

    def __init__(
        self,
        agent_name: str,
        conversation_id: Optional[str] = None,
        user: Optional[Any] = None,
        **kwargs: Any,
    ):
        """
        Initialize memory backend.

        Args:
            agent_name: Name of the agent using this memory
            conversation_id: Optional existing conversation ID to resume
            user: Optional user to associate with conversation
            **kwargs: Additional configuration
        """
        self.agent_name = agent_name
        self.conversation_id = conversation_id
        self.user = user
        self._initialized = False

    @abstractmethod
    def initialize(self) -> None:
        """
        Initialize the memory backend.

        Create or load the conversation.
        """
        pass

    @abstractmethod
    def add_message(self, role: str, content: str, **metadata: Any) -> None:
        """
        Add a message to the conversation.

        Args:
            role: Message role ('human', 'ai', 'system')
            content: Message content
            **metadata: Additional metadata to store
        """
        pass

    @abstractmethod
    def get_messages(self, limit: Optional[int] = None) -> List[Any]:
        """
        Get conversation messages.

        Args:
            limit: Maximum number of messages to return

        Returns:
            List of messages (format depends on backend)
        """
        pass

    @abstractmethod
    def get_messages_as_langchain(self, limit: Optional[int] = None) -> List[Any]:
        """
        Get messages as LangChain message objects.

        Args:
            limit: Maximum number of messages to return

        Returns:
            List of LangChain message objects
        """
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all messages in the conversation."""
        pass

    @abstractmethod
    def get_conversation_info(self) -> Dict[str, Any]:
        """
        Get conversation metadata.

        Returns:
            Dictionary with conversation information
        """
        pass

    def __len__(self) -> int:
        """Return the number of messages in the conversation."""
        messages = self.get_messages()
        return len(messages)

    def get_state(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Return persisted runtime state for a thread if supported."""
        return None

    def save_state(self, thread_id: str, state: Dict[str, Any]) -> None:
        """Persist runtime state for a thread if supported."""

    def clear_state(self, thread_id: str) -> None:
        """Clear persisted runtime state for a thread if supported."""
