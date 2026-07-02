from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.knowledge_base.retriever import KnowledgeBaseRetriever
from app.ai.providers import get_ai_provider
from app.ai.providers.base import Message, MessageRole
from app.core.logging import get_logger

logger = get_logger(__name__)

RAG_SYSTEM_PROMPT = """You are a helpful AI assistant for a WhatsApp CRM platform.
Answer questions using ONLY the provided context. If the answer is not in the context, say so honestly.
Be concise, accurate, and cite which document your answer comes from when possible.
"""


class RAGService:
    """Retrieval-Augmented Generation — answers queries from the knowledge base."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.retriever = KnowledgeBaseRetriever(session)
        self.provider = get_ai_provider()

    async def answer(
        self,
        query: str,
        *,
        limit: int = 5,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        # Step 1: Retrieve relevant chunks
        chunks = await self.retriever.search(query, limit=limit)

        if not chunks:
            return {
                "answer": "I don't have information about that in the knowledge base.",
                "sources": [],
                "chunks_used": 0,
            }

        # Step 2: Build context from top chunks
        context = "\n\n---\n\n".join([
            f"[Source: {c['document_title']}]\n{c['content']}"
            for c in chunks
        ])

        # Step 3: Build messages
        messages: list[Message] = [
            Message(role=MessageRole.SYSTEM, content=RAG_SYSTEM_PROMPT),
        ]

        # Include prior conversation turns if provided
        if conversation_history:
            for turn in conversation_history[-6:]:
                role = MessageRole.USER if turn.get("role") == "user" else MessageRole.ASSISTANT
                messages.append(Message(role=role, content=turn.get("content", "")))

        messages.append(Message(
            role=MessageRole.USER,
            content=f"Context:\n{context}\n\nQuestion: {query}",
        ))

        # Step 4: Generate answer
        response = await self.provider.complete(messages=messages, temperature=0.2)

        sources = list({c["document_title"] for c in chunks})

        return {
            "answer": response.content.strip(),
            "sources": sources,
            "chunks_used": len(chunks),
            "chunks": [
                {
                    "document_title": c["document_title"],
                    "similarity": c["similarity"],
                    "excerpt": c["content"][:300] + "..." if len(c["content"]) > 300 else c["content"],
                }
                for c in chunks
            ],
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
        }

    async def answer_with_crm_context(
        self,
        query: str,
        customer_id: str | None = None,
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        """RAG answer enriched with customer CRM context."""
        extra_context = ""

        if customer_id:
            from sqlalchemy import select
            import uuid
            from app.models.customer import Customer
            from app.models.note import Note

            try:
                cid = uuid.UUID(customer_id)
                customer = await self.session.get(Customer, cid)
                if customer:
                    extra_context += (
                        f"\nCustomer context: {customer.full_name}, "
                        f"Industry: {customer.industry or 'unknown'}, "
                        f"Status: {customer.status}, "
                        f"Lead score: {customer.lead_score}"
                    )
                    # Include recent notes
                    notes_result = await self.session.execute(
                        select(Note)
                        .where(Note.customer_id == cid)
                        .order_by(Note.created_at.desc())
                        .limit(3)
                    )
                    notes = notes_result.scalars().all()
                    if notes:
                        extra_context += "\nRecent notes: " + " | ".join(n.content[:100] for n in notes)
            except (ValueError, Exception):
                pass

        enriched_query = query + extra_context
        return await self.answer(enriched_query)
