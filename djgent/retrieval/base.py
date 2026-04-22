"""Retrieval primitives for Djgent knowledge workflows."""

from __future__ import annotations

from typing import Any, Dict, List


class BaseRetriever:
    """Minimal retriever interface used by Djgent."""

    def get_relevant_documents(self, query: str, **kwargs: Any) -> List[Dict[str, Any]]:
        """Return relevant documents for a query."""
        raise NotImplementedError


class DjangoKnowledgeRetriever(BaseRetriever):
    """Simple database-backed retriever over KnowledgeDocument.

    Uses database-level ``icontains`` filtering to narrow the candidate
    set before applying in-memory term-frequency scoring.  This avoids
    loading hundreds of irrelevant documents into memory for every query.
    """

    def __init__(self, namespace: str = "default"):
        self.namespace = namespace

    def get_relevant_documents(self, query: str, **kwargs: Any) -> List[Dict[str, Any]]:
        from django.db.models import Q

        from djgent.models import KnowledgeDocument

        limit = int(kwargs.get("limit", 5))
        terms = [term for term in query.split() if term.strip()]

        if not terms:
            return []

        # Build a database-level OR filter so the DB does the heavy lifting.
        q_filter = Q()
        for term in terms:
            q_filter |= Q(title__icontains=term) | Q(content__icontains=term)

        queryset = KnowledgeDocument.objects.filter(q_filter, namespace=self.namespace)[:200]

        results = []
        terms_lower = [t.lower() for t in terms]

        for document in queryset:
            haystack = f"{document.title}\n{document.content}".lower()
            score = sum(haystack.count(term) for term in terms_lower)
            if score <= 0:
                continue
            results.append(
                {
                    "id": document.id,
                    "title": document.title,
                    "content": document.content,
                    "source": document.source,
                    "metadata": document.metadata,
                    "score": score,
                }
            )

        results.sort(key=lambda item: item["score"], reverse=True)
        return results[:limit]
