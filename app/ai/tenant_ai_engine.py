"""
Updated AI engine — uses tenant AI credentials instead of global settings.
Update app/ai/crm_engine.py to use this pattern.
"""
from __future__ import annotations

from app.ai.providers import get_ai_provider
from app.models.tenant import Tenant
from app.core.config import settings


def get_ai_provider_for_tenant(tenant: Tenant | None = None):
    """
    Get AI provider using tenant credentials if available,
    otherwise fall back to global settings.
    """
    if not tenant:
        return get_ai_provider()

    # Use tenant's AI provider and key if configured
    provider_name = tenant.ai_provider or settings.AI_PROVIDER
    api_key = tenant.ai_api_key

    if not api_key:
        # Fall back to global settings
        return get_ai_provider()

    # Create provider with tenant credentials
    if provider_name == "openai":
        from app.ai.providers.openai_provider import OpenAIProvider
        return OpenAIProvider(api_key=api_key, model=tenant.ai_model)

    elif provider_name == "gemini":
        from app.ai.providers.gemini_provider import GeminiProvider
        return GeminiProvider(api_key=api_key, model=tenant.ai_model)

    # Default fallback
    return get_ai_provider()


class TenantAwareCRMEngine:
    """
    Extended AI CRM engine that uses tenant-specific credentials.
    Wraps the existing AICRMEngine with tenant context.
    """

    def __init__(self, session, tenant: Tenant) -> None:
        from app.ai.crm_engine import AICRMEngine
        self.engine = AICRMEngine(session, tenant_id=tenant.id)
        self.tenant = tenant

        # Override the provider with tenant-specific one
        self.engine.provider = get_ai_provider_for_tenant(tenant)

    async def process_message(self, message, customer, history):
        return await self.engine.process_message(message, customer, history)

    async def analyze_message(self, message, customer, history):
        return await self.engine.analyze_message(message, customer, history)

    async def qualify_lead(self, customer, conversation_text):
        return await self.engine.qualify_lead(customer, conversation_text)

    async def generate_suggested_reply(self, customer, history, context=""):
        return await self.engine.generate_suggested_reply(
            customer, history, context
        )

    async def summarize_conversation(self, messages, customer):
        return await self.engine.summarize_conversation(messages, customer)
