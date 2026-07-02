from __future__ import annotations

import json
import math
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers import get_ai_provider
from app.models.knowledge_document import DocumentChunk, DocumentStatus, KnowledgeDocument


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x ** 2 for x in a))
    norm_b = math.sqrt(sum(x ** 2 for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class KnowledgeBaseRetriever:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.provider = get_ai_provider()

    async def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        query_embedding = await self.provider.embed_single(query)

        stmt = (
            select(DocumentChunk, KnowledgeDocument.title)
            .join(KnowledgeDocument, KnowledgeDocument.id == DocumentChunk.document_id)
            .where(KnowledgeDocument.status == DocumentStatus.READY)
            .where(DocumentChunk.embedding.isnot(None))
        )
        result = await self.session.execute(stmt)
        rows = result.all()

        scored = []
        for chunk, doc_title in rows:
            if chunk.embedding:
                embedding = chunk.embedding if isinstance(chunk.embedding, list) else json.loads(chunk.embedding)
                score = cosine_similarity(query_embedding, embedding)
                scored.append({
                    "chunk_id": str(chunk.id),
                    "document_id": str(chunk.document_id),
                    "document_title": doc_title,
                    "content": chunk.content,
                    "similarity": round(score, 4),
                })

        scored.sort(key=lambda x: x["similarity"], reverse=True)
        return scored[:limit]

    async def get_context_for_query(self, query: str, limit: int = 5) -> str:
        results = await self.search(query, limit=limit)
        if not results:
            return ""
        context_parts = [
            f"[Source: {r['document_title']}]\n{r['content']}"
            for r in results
        ]
        return "\n\n---\n\n".join(context_parts)
