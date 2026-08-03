from __future__ import annotations

import json
import re
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers import get_ai_provider
from app.ai.providers.base import Message, MessageRole, ToolDefinition
from app.core.logging import get_logger
from app.models.activity import ActivityType
from app.models.conversation import ConversationMessage
from app.models.customer import Customer
from app.repositories.crm import ActivityRepository, CustomerRepository
from app.services.crm import LeadService, NoteService, TaskService

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are an AI-powered CRM assistant for a WhatsApp business platform.
Your job is to:
1. Analyze customer messages and extract intent, sentiment, entities, and urgency.
2. Update CRM records automatically with relevant information.
3. Generate follow-up tasks, notes, and lead qualification data.
4. Recommend products or services based on conversation context.
5. Detect when to escalate to a human agent.

Always respond in the customer's language. Be professional, friendly, and concise.
When extracting data, return valid JSON in the specified format.
"""

ANALYSIS_PROMPT = """Analyze this customer message and return ONLY a valid JSON object.
No explanation, no markdown, no code blocks. Just the raw JSON starting with {{ and ending with }}.

Return exactly this structure:
{{
  "intent": "purchase|inquiry|complaint|support|booking|general",
  "sentiment": "positive|neutral|negative",
  "sentiment_score": 0.0,
  "urgency": "low|medium|high|critical",
  "language": "en",
  "entities": {{
    "product_mentioned": null,
    "budget": null,
    "timeline": null,
    "location": null,
    "contact_info": null
  }},
  "lead_score_delta": 0,
  "should_escalate": false,
  "escalation_reason": null,
  "suggested_reply": "A helpful reply in the customer language",
  "action_items": [],
  "crm_notes": "internal note"
}}

Customer message: {message}
Customer profile: {profile}
Conversation history: {history}
"""


class AICRMEngine:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.provider = get_ai_provider()
        self.customer_repo = CustomerRepository(session)
        self.activity_repo = ActivityRepository(session)
        self.note_service = NoteService(session)
        self.task_service = TaskService(session)
        self.lead_service = LeadService(session)

    async def analyze_message(
        self,
        message: ConversationMessage,
        customer: Customer,
        history: list[ConversationMessage],
    ) -> dict[str, Any]:
        history_text = "\n".join([
            f"{'Customer' if m.direction == 'inbound' else 'Agent'}: {m.content or ''}"
            for m in history[-10:]
        ])
        profile_text = (
            f"Name: {customer.full_name}, Phone: {customer.phone}, "
            f"Status: {customer.status}, Lead Score: {customer.lead_score}, "
            f"Industry: {customer.industry or 'Unknown'}"
        )

        prompt = ANALYSIS_PROMPT.format(
            message=message.content or "",
            profile=profile_text,
            history=history_text,
        )

        response = await self.provider.complete(
            messages=[
                Message(role=MessageRole.SYSTEM, content=SYSTEM_PROMPT),
                Message(role=MessageRole.USER, content=prompt),
            ],
            temperature=0.3,
        )

        # Clean and parse the response
        raw = response.content.strip()
        raw = re.sub(r'```json\s*|\s*```', '', raw).strip()

        try:
            analysis = json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match:
                try:
                    analysis = json.loads(match.group())
                except json.JSONDecodeError:
                    logger.warning(
                        "AI returned unparseable response",
                        content=raw[:300],
                    )
                    analysis = {
                        "intent": "general",
                        "sentiment": "neutral",
                        "sentiment_score": 0.5,
                        "urgency": "low",
                        "language": "en",
                        "entities": {},
                        "lead_score_delta": 0,
                        "should_escalate": False,
                        "escalation_reason": None,
                        "suggested_reply": "",
                        "action_items": [],
                        "crm_notes": "",
                    }
            else:
                logger.warning(
                    "AI returned unparseable response",
                    content=raw[:300],
                )
                analysis = {
                    "intent": "general",
                    "sentiment": "neutral",
                    "sentiment_score": 0.5,
                    "urgency": "low",
                    "language": "en",
                    "entities": {},
                    "lead_score_delta": 0,
                    "should_escalate": False,
                    "escalation_reason": None,
                    "suggested_reply": "",
                    "action_items": [],
                    "crm_notes": "",
                }

        logger.info(
            "Message analyzed",
            intent=analysis.get("intent"),
            sentiment=analysis.get("sentiment"),
            should_escalate=analysis.get("should_escalate"),
        )

        return analysis

    async def process_message(
        self,
        message: ConversationMessage,
        customer: Customer,
        history: list[ConversationMessage],
    ) -> dict[str, Any]:
        analysis = await self.analyze_message(message, customer, history)

        # Update customer CRM data
        updates: dict[str, Any] = {}
        if analysis.get("sentiment_score") is not None:
            updates["sentiment_score"] = analysis["sentiment_score"]
        if analysis.get("intent"):
            updates["intent_summary"] = analysis["intent"]
        if analysis.get("language"):
            updates["language"] = analysis.get("language")

        score_delta = analysis.get("lead_score_delta", 0)
        if score_delta:
            updates["lead_score"] = max(0, min(100, customer.lead_score + score_delta))

        entities = analysis.get("entities", {})
        if entities.get("location"):
            updates["city"] = entities["location"]

        if updates:
            await self.customer_repo.update(customer, **updates)

        # Create AI note
        crm_notes = analysis.get("crm_notes")
        if crm_notes:
            from app.schemas.crm import NoteCreate
            await self.note_service.create(
                NoteCreate(
                    customer_id=customer.id,
                    title="AI Analysis",
                    content=crm_notes,
                ),
                created_by=None,
            )

        # Create action tasks
        for action in analysis.get("action_items", [])[:3]:
            from app.schemas.crm import TaskCreate
            await self.task_service.create(
                TaskCreate(
                    title=action,
                    customer_id=customer.id,
                    description="AI-generated from conversation analysis",
                )
            )

        # Log activity
        await self.activity_repo.log(
            customer_id=customer.id,
            activity_type=ActivityType.AI_INTERACTION,
            title=f"AI processed message — intent: {analysis.get('intent', 'unknown')}",
            description=f"Sentiment: {analysis.get('sentiment')}, Urgency: {analysis.get('urgency')}",
            metadata={
                "intent": analysis.get("intent"),
                "sentiment": analysis.get("sentiment"),
                "urgency": analysis.get("urgency"),
                "should_escalate": analysis.get("should_escalate"),
            },
        )

        return analysis

    async def qualify_lead(
        self,
        customer: Customer,
        conversation_text: str,
    ) -> dict[str, Any]:
        prompt = f"""Qualify this lead based on the conversation.
Return ONLY a valid JSON object with no extra text, no markdown, no code blocks.

Return exactly this structure:
{{
  "lead_score": 0,
  "buying_intent": "none|low|medium|high|very_high",
  "budget_range": null,
  "timeline": null,
  "is_decision_maker": null,
  "purchase_probability": 0.0,
  "urgency": "low|medium|high|critical",
  "industry": null,
  "business_size": "micro|small|medium|large|enterprise|null",
  "qualification_notes": "notes"
}}

Customer: {customer.full_name}, Industry: {customer.industry}
Conversation:
{conversation_text}
"""
        response = await self.provider.complete(
            messages=[
                Message(
                    role=MessageRole.SYSTEM,
                    content="You are a lead qualification expert. Return only valid JSON with no extra text.",
                ),
                Message(role=MessageRole.USER, content=prompt),
            ],
            temperature=0.2,
        )

        raw = response.content.strip()
        raw = re.sub(r'```json\s*|\s*```', '', raw).strip()

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            logger.warning("Could not parse lead qualification response", content=raw[:300])
            return {}

    async def generate_suggested_reply(
        self,
        customer: Customer,
        conversation_history: list[ConversationMessage],
        context: str = "",
    ) -> str:
        history_text = "\n".join([
            f"{'Customer' if m.direction == 'inbound' else 'Agent'}: {m.content or ''}"
            for m in conversation_history[-15:]
        ])
        prompt = f"""Generate a professional, friendly WhatsApp reply for this customer.
Customer: {customer.full_name}
Language preference: {customer.language or 'en'}
Context: {context}

Conversation:
{history_text}

Reply should be concise (max 3 sentences), warm, and actionable.
Return only the reply text, no extra explanation.
"""
        response = await self.provider.complete(
            messages=[
                Message(role=MessageRole.SYSTEM, content=SYSTEM_PROMPT),
                Message(role=MessageRole.USER, content=prompt),
            ],
            temperature=0.7,
        )
        return response.content.strip()

    async def summarize_conversation(
        self,
        messages: list[ConversationMessage],
        customer: Customer,
    ) -> str:
        if not messages:
            return ""
        conversation_text = "\n".join([
            f"{'Customer' if m.direction == 'inbound' else 'Agent'}: {m.content or '[media]'}"
            for m in messages
        ])
        prompt = f"""Summarize this WhatsApp conversation for CRM records.
Customer: {customer.full_name}

Conversation:
{conversation_text}

Provide a concise summary covering: main topics, customer needs, action items, and outcome.
"""
        response = await self.provider.complete(
            messages=[Message(role=MessageRole.USER, content=prompt)],
            temperature=0.3,
            max_tokens=500,
        )
        return response.content.strip()