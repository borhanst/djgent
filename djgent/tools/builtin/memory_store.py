"""Built-in long-term memory tool."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from djgent.memory.store import memory_store
from djgent.tools.base import Tool


class MemoryStoreTool(Tool):
    """Persist and recall long-term memory facts."""

    name = "memory_store"
    description = "Store, recall, and list long-term memory facts for Djgent agents."
    risk_level = "medium"
    requires_approval = True
    approval_reason = "Long-term memory writes persist user or conversation facts."

    def _run(
        self,
        action: str,
        key: Optional[str] = None,
        value: Optional[str] = None,
        scope: str = "user",
        runtime: Optional[Any] = None,
        limit: int = 25,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        user = self._get_user(runtime)
        conversation = None
        django_ctx = self._get_django_context(runtime)
        if django_ctx:
            conversation = getattr(django_ctx, "conversation", None)

        if action == "put":
            if not key or value is None:
                return json.dumps({"error": "key and value are required for put"})
            fact = memory_store.put(
                key,
                value,
                scope=scope,
                user=user,
                conversation=conversation,
                metadata=metadata,
            )
            return json.dumps({"key": fact.key, "scope": fact.scope, "value": fact.value})

        if action == "get":
            if not key:
                return json.dumps({"error": "key is required for get"})
            result = memory_store.get(key, scope=scope, user=user, conversation=conversation)
            return json.dumps({"key": key, "scope": scope, "value": result})

        if action == "list":
            facts = memory_store.list(
                scope=scope,
                user=user,
                conversation=conversation,
                limit=limit,
            )
            return json.dumps({"scope": scope, "count": len(facts), "facts": facts})

        return json.dumps({"error": f"Unknown action '{action}'"})
