"""Tools for knowledge retrieval and ingestion."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from djgent.retrieval.base import DjangoKnowledgeRetriever
from djgent.tools.base import Tool


class RetrievalTool(Tool):
    """Query a retriever-backed knowledge base."""

    name = "knowledge_retrieval"
    description = (
        "Search Djgent knowledge documents and return relevant context."
    )
    risk_level = "low"

    def __init__(
        self,
        retriever: Optional[Any] = None,
        namespace: str = "default",
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self.namespace = namespace
        self.retriever = retriever or DjangoKnowledgeRetriever(
            namespace=namespace
        )

    def _run(self, query: str, limit: int = 5, **kwargs: Any) -> str:
        documents = self.retriever.get_relevant_documents(
            query, limit=limit, **kwargs
        )
        return json.dumps(
            {
                "query": query,
                "count": len(documents),
                "documents": documents,
            }
        )


class KnowledgeIngestTool(Tool):
    """Store plain-text knowledge documents for retrieval workflows."""

    name = "knowledge_ingest"
    description = "Ingest a text document into the Djgent knowledge base."
    risk_level = "medium"
    requires_approval = True
    approval_reason = "Knowledge ingestion writes persistent retrieval data."

    def _run(
        self,
        title: str,
        content: str,
        namespace: str = "default",
        source: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> str:
        from djgent.models import KnowledgeDocument

        document = KnowledgeDocument.objects.create(
            namespace=namespace,
            title=title,
            content=content,
            source=source,
            metadata=metadata or {},
        )
        return json.dumps(
            {
                "id": document.id,
                "namespace": document.namespace,
                "title": document.title,
            }
        )
