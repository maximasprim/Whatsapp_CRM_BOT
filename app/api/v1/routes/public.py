# from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.base import get_db
from app.core.exceptions import ConflictException
from app.core.logging import get_logger
from app.core.rate_limit import limiter
from app.models.lead import LeadPriority, LeadSource, LeadStatus
from app.models.tenant import Tenant
from app.repositories.crm import CustomerRepository
from app.schemas.crm import CustomerCreate, LeadCreate
from app.schemas.public import PublicLeadRequest, PublicLeadResponse
from app.services.crm import CustomerService, LeadService
from app.services.lead_notifications import notify_agents_of_new_lead
from app.tenant.middleware import get_current_tenant
from app.whatsapp.conversation_service import WhatsAppConversationService
from app.core.config import settings

logger = get_logger(__name__)

router = APIRouter(prefix="/public", tags=["Public"])

# Human-readable label for the lead title, keyed by the site's source_page
# value. Falls back to the raw value if the site sends a page we don't
# recognize yet, so adding a new page on the website never breaks this.
_SOURCE_LABELS = {
    "calculator": "Loan Calculator",
    "contact": "Contact Form",
    "apply": "Loan Application",
}


@router.post("/leads", response_model=PublicLeadResponse, status_code=201)
@limiter.limit("5/hour")
async def create_public_lead(
    request: Request,
    data: PublicLeadRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_tenant: Annotated[Tenant, Depends(get_current_tenant)],
) -> PublicLeadResponse:
    """
    Unauthenticated ingestion point for the marketing website. Deliberately
    forgiving: a real visitor should never see an error here just because
    they already exist as a customer, so an existing phone number is
    treated as a hand-off to lead creation rather than a conflict.

    Tenant is resolved from the request itself (X-Tenant-Slug header,
    subdomain, or custom domain) since this endpoint is unauthenticated —
    each tenant's marketing site posts leads to its own tenant this way.
    """
    if data.hp:
        # Honeypot tripped - silently pretend success so the bot moves on.
        return PublicLeadResponse(success=True)

    customer_repo = CustomerRepository(session, tenant_id=current_tenant.id)
    customer_service = CustomerService(session, tenant_id=current_tenant.id)
    lead_service = LeadService(session, tenant_id=current_tenant.id)

    first, *rest = data.full_name.strip().split(" ", 1)
    last = rest[0] if rest else ""

    existing = await customer_repo.get_by_phone(data.phone)
    if existing:
        customer = existing
    else:
        try:
            customer = await customer_service.create(
                CustomerCreate(
                    first_name=first,
                    last_name=last,
                    phone=data.phone,
                    email=data.email,
                    source="website",
                )
            )
        except ConflictException:
            # Lost a race with another request for the same phone number.
            customer = await customer_repo.get_by_phone(data.phone)
            if customer is None:
                raise

    source_label = _SOURCE_LABELS.get(data.source_page, data.source_page)
    title = f"Website lead - {source_label}"
    if data.product_interest:
        title += f" ({data.product_interest})"

    description_parts = [f"Trigger: {data.trigger}"]
    if data.message:
        description_parts.append(data.message)
    description = "\n\n".join(description_parts)

    lead = await lead_service.create(
        LeadCreate(
            title=title,
            description=description,
            customer_id=customer.id,
            status=LeadStatus.NEW,
            priority=LeadPriority.MEDIUM,
            source=LeadSource.WEBSITE,
        )
    )

    logger.info(
        "public_lead_created",
        customer_id=str(customer.id),
        lead_id=str(lead.id),
        source_page=data.source_page,
        trigger=data.trigger,
    )

    try:
        await notify_agents_of_new_lead(
            session,
            tenant_id=current_tenant.id,
            lead_id=lead.id,
            lead_title=title,
            customer_name=data.full_name,
            customer_phone=customer.phone,
        )
    except Exception:
        # Same principle as the WhatsApp send below - never fail lead
        # creation because a downstream notification step failed.
        logger.exception("lead_agent_notification_failed", lead_id=str(lead.id))

    if settings.WHATSAPP_WEBSITE_LEAD_TEMPLATE_NAME:
        try:
            wa_service = WhatsAppConversationService(session, tenant=current_tenant)
            await wa_service.initiate_conversation(
                customer_id=customer.id,
                phone=customer.phone,
                template_name=settings.WHATSAPP_WEBSITE_LEAD_TEMPLATE_NAME,
                template_language=settings.WHATSAPP_WEBSITE_LEAD_TEMPLATE_LANGUAGE,
                template_components=[
                    {"type": "body", "parameters": [{"type": "text", "text": first or "there"}]}
                ],
                source_note=f"Auto-started from website lead ({source_label}).",
            )
        except Exception:
            # A WhatsApp/template failure should never fail lead creation -
            # the lead already exists in the CRM either way, an agent can
            # always reach out manually.
            logger.exception(
                "whatsapp_conversation_initiate_failed",
                customer_id=str(customer.id),
                lead_id=str(lead.id),
            )

    return PublicLeadResponse(success=True, customer_id=customer.id, lead_id=lead.id)
