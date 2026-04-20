"""Long-term memory store helpers."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class MemoryStore:
    """Persist reusable facts across conversations."""

    def put(
        self,
        key: str,
        value: str,
        *,
        scope: str = "user",
        agent_name: str = "",
        user: Optional[Any] = None,
        conversation: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Create or update a memory fact."""
        from djgent.models import MemoryFact

        fact, _ = MemoryFact.objects.update_or_create(
            scope=scope,
            key=key,
            user=user,
            conversation=conversation,
            defaults={
                "value": value,
                "agent_name": agent_name,
                "metadata": metadata or {},
            },
        )
        return fact

    def get(
        self,
        key: str,
        *,
        scope: str = "user",
        user: Optional[Any] = None,
        conversation: Optional[Any] = None,
    ) -> Optional[str]:
        """Return a stored fact value."""
        from djgent.models import MemoryFact

        fact = (
            MemoryFact.objects.filter(
                scope=scope,
                key=key,
                user=user,
                conversation=conversation,
            )
            .order_by("-updated_at")
            .first()
        )
        return fact.value if fact else None

    def list(
        self,
        *,
        scope: Optional[str] = None,
        user: Optional[Any] = None,
        conversation: Optional[Any] = None,
        agent_name: str = "",
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List persisted facts."""
        from djgent.models import MemoryFact

        queryset = MemoryFact.objects.all().order_by("-updated_at")
        if scope:
            queryset = queryset.filter(scope=scope)
        if user is not None:
            queryset = queryset.filter(user=user)
        if conversation is not None:
            queryset = queryset.filter(conversation=conversation)
        if agent_name:
            queryset = queryset.filter(agent_name=agent_name)

        return [
            {
                "key": item.key,
                "value": item.value,
                "scope": item.scope,
                "agent_name": item.agent_name,
                "metadata": item.metadata,
            }
            for item in queryset[:limit]
        ]


memory_store = MemoryStore()
