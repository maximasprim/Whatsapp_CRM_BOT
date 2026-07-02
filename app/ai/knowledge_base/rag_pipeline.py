from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.knowledge_base.retriever import KnowledgeBaseRetriever
from app.ai.providers import get_ai_provider
from app.ai.providers.base import Message, MessageRole
from app.core.logging import get_logger

logger = get_logger(__name__)

RAG_SYSTEM_PROMPT = """You are a helpful, knowledgeable customer support assistant for a business using WhatsApp.
Answer the customer's question using ONLY the provided context from the knowledge base.
If the context doesn't contain the answer, say you don't have that information and offer to connect them with a human agent.
Always cite which source document your answer comes from when possible.
Keep answers concise and conversational, suitable for WhatsApp (2-4 sentences max unless more detail is explicitly requested).
"""

RAG_USER_PROMPT_TEMPLATE = """Context from knowledge base:
{context}

Customer question: {question}

Provide a helpful, accurate answer based only on the context above. If you cite a source, mention the document title.
"""


@dataclass
class RAGCitation:
    document_id: str
    document_title: str
    chunk_id: str
    similarity: float


@dataclass
class RAGResponse:
    answer: str
    citations: list[RAGCitation] = field(default_factory=list)
    context_found: bool = True
    confidence: float = 0.0


class RAGPipeline:
    """Full Retrieval-Augmented Generation pipeline: retrieve relevant chunks,
    rank by relevance, inject as context, and generate a grounded answer with citations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.retriever = KnowledgeBaseRetriever(session)
        self.provider = get_ai_provider()

    async def answer_question(
        self,
        question: str,
        top_k: int = 5,
        min_similarity: float = 0.3,
        conversation_context: str = "",
    ) -> RAGResponse:
        results = await self.retriever.search(question, limit=top_k)
        relevant_results = [r for r in results if r["similarity"] >= min_similarity]

        if not relevant_results:
            logger.info("No relevant knowledge base context found", question=question[:100])
            return RAGResponse(
                answer="I don't have specific information about that in my knowledge base. Let me connect you with a team member who can help further.",
                citations=[],
                context_found=False,
                confidence=0.0,
            )

        context_parts = [
            f"[Document: {r['document_title']}]\n{r['content']}"
            for r in relevant_results
        ]
        context = "\n\n---\n\n".join(context_parts)

        user_prompt = RAG_USER_PROMPT_TEMPLATE.format(context=context, question=question)
        if conversation_context:
            user_prompt = f"Recent conversation context:\n{conversation_context}\n\n{user_prompt}"

        response = await self.provider.complete(
            messages=[
                Message(role=MessageRole.SYSTEM, content=RAG_SYSTEM_PROMPT),
                Message(role=MessageRole.USER, content=user_prompt),
            ],
            temperature=0.3,
            max_tokens=500,
        )

        citations = [
            RAGCitation(
                document_id=r["document_id"],
                document_title=r["document_title"],
                chunk_id=r["chunk_id"],
                similarity=r["similarity"],
            )
            for r in relevant_results
        ]

        avg_confidence = sum(r["similarity"] for r in relevant_results) / len(relevant_results)

        return RAGResponse(
            answer=response.content.strip(),
            citations=citations,
            context_found=True,
            confidence=round(avg_confidence, 4),
        )

    async def answer_with_fallback_to_human(
        self, question: str, confidence_threshold: float = 0.4
    ) -> tuple[RAGResponse, bool]:
        """Returns (response, should_escalate_to_human)."""
        response = await self.answer_question(question)
        should_escalate = not response.context_found or response.confidence < confidence_threshold
        return response, should_escalate
