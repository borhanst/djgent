"""Utility functions for djgent memory management."""

from datetime import timedelta
from typing import Any, Dict, List, Optional

from django.utils import timezone


def create_conversation(
    agent_name: str,
    name: str = "",
    user: Any = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Create a new conversation.

    Args:
        agent_name: Name of the agent
        name: Optional conversation name
        user: Optional user to associate
        metadata: Optional metadata dictionary

    Returns:
        Conversation ID (UUID string)

    Example:
        conv_id = create_conversation("assistant", user=request.user)
    """
    from djgent.models import Conversation

    conversation = Conversation.objects.create(
        agent_name=agent_name,
        name=name,
        user=user,
        metadata=metadata or {},
    )
    return str(conversation.id)


def get_conversation(conversation_id: str) -> Optional[Any]:
    """
    Get a conversation by ID.

    Args:
        conversation_id: Conversation UUID

    Returns:
        Conversation object or None if not found

    Example:
        conversation = get_conversation(conv_id)
        if conversation:
            messages = conversation.messages.all()
    """
    from djgent.models import Conversation

    try:
        return Conversation.objects.get(id=conversation_id)
    except Conversation.DoesNotExist:
        return None


def delete_conversation(conversation_id: str) -> bool:
    """
    Delete a conversation and all its messages.

    Args:
        conversation_id: Conversation UUID

    Returns:
        True if deleted, False if not found

    Example:
        deleted = delete_conversation(conv_id)
    """
    from djgent.models import Conversation

    try:
        conversation = Conversation.objects.get(id=conversation_id)
        conversation.delete()
        return True
    except Conversation.DoesNotExist:
        return False


def get_all_conversations(
    user: Any = None,
    agent_name: Optional[str] = None,
    limit: Optional[int] = None,
    offset: int = 0,
) -> List[Any]:
    """
    Get conversations with optional filters.

    Args:
        user: Filter by user
        agent_name: Filter by agent name
        limit: Maximum number of conversations
        offset: Pagination offset

    Returns:
        List of Conversation objects

    Example:
        # Get user's conversations
        conversations = get_all_conversations(user=request.user)

        # Get conversations for specific agent
        conversations = get_all_conversations(agent_name="assistant", limit=10)
    """
    from djgent.models import Conversation

    queryset = Conversation.objects.all()

    if user:
        queryset = queryset.filter(user=user)

    if agent_name:
        queryset = queryset.filter(agent_name=agent_name)

    if limit:
        queryset = queryset[offset : offset + limit]

    return list(queryset)


def get_conversation_messages(
    conversation_id: str,
    limit: Optional[int] = None,
) -> List[Any]:
    """
    Get messages from a conversation.

    Args:
        conversation_id: Conversation UUID
        limit: Maximum number of messages

    Returns:
        List of Message objects

    Example:
        messages = get_conversation_messages(conv_id, limit=20)
    """
    from djgent.models import Message

    queryset = Message.objects.filter(conversation_id=conversation_id)
    if limit:
        queryset = queryset[:limit]
    return list(queryset)


def clear_old_conversations(
    days: int = 30,
    user: Any = None,
    dry_run: bool = False,
) -> Dict[str, int]:
    """
    Delete conversations older than specified days.

    Args:
        days: Delete conversations older than this many days
        user: Optional user filter
        dry_run: If True, don't actually delete

    Returns:
        Dictionary with statistics

    Example:
        # Delete conversations older than 90 days
        result = clear_old_conversations(days=90)
        print(f"Deleted {result['deleted']} conversations")

        # Preview what would be deleted
        result = clear_old_conversations(days=90, dry_run=True)
    """
    from djgent.models import Conversation

    cutoff_date = timezone.now() - timedelta(days=days)
    queryset = Conversation.objects.filter(updated_at__lt=cutoff_date)

    if user:
        queryset = queryset.filter(user=user)

    count = queryset.count()

    if not dry_run:
        queryset.delete()

    return {
        "deleted": count if not dry_run else 0,
        "would_delete": count,
        "dry_run": dry_run,
        "cutoff_date": cutoff_date.isoformat(),
    }


def export_conversation(conversation_id: str, format: str = "json") -> Any:
    """
    Export a conversation to a specified format.

    Args:
        conversation_id: Conversation UUID
        format: Export format ('json', 'dict')

    Returns:
        Exported conversation data

    Example:
        data = export_conversation(conv_id, format="json")
    """
    import json

    from djgent.models import Conversation

    try:
        conversation = Conversation.objects.get(id=conversation_id)
    except Conversation.DoesNotExist:
        return None

    # Get messages
    messages = []
    for msg in conversation.messages.all():
        messages.append(
            {
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "created_at": msg.created_at.isoformat(),
                "metadata": msg.metadata,
            }
        )

    # Build export data
    data = {
        "conversation": conversation.to_dict(),
        "messages": messages,
    }

    if format == "json":
        return json.dumps(data, indent=2)

    return data


def import_conversation(
    data: Dict[str, Any],
    agent_name: Optional[str] = None,
    user: Any = None,
) -> str:
    """
    Import a conversation from exported data.

    Args:
        data: Conversation data dictionary
        agent_name: Override agent name (optional)
        user: Override user (optional)

    Returns:
        New conversation ID

    Example:
        new_id = import_conversation(data, user=request.user)
    """
    from djgent.models import Conversation, Message

    conv_data = data.get("conversation", data)
    messages_data = data.get("messages", [])

    # Create conversation
    conversation = Conversation.objects.create(
        agent_name=agent_name or conv_data.get("agent_name", "imported"),
        name=conv_data.get("name", ""),
        user=user,
        metadata=conv_data.get("metadata", {}),
    )

    # Import messages
    for msg_data in messages_data:
        Message.objects.create(
            conversation=conversation,
            role=msg_data.get("role", "human"),
            content=msg_data.get("content", ""),
            metadata=msg_data.get("metadata", {}),
        )

    return str(conversation.id)
