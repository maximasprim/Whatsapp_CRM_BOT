"""
Billing routes — checkout, portal, usage, webhooks.
Add to app/api/v1/routes/billing.py
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_tenant_from_user, get_current_user
from app.core.database.base import get_db
from app.core.logging import get_logger
from app.models.auth import User
from app.models.tenant import Tenant
from app.schemas.common import SuccessResponse
from app.billing.stripe_service import PLANS, StripeService
from app.usage.tracker import UsageTracker

logger = get_logger(__name__)
router = APIRouter(prefix="/billing", tags=["Billing"])


@router.get("/plans")
async def list_plans() -> dict:
    """Get all available plans and their features."""
    return {
        "plans": [
            {
                "id": plan_id,
                "name": config["name"],
                "price_monthly": config["price_monthly"] / 100,
                "currency": "usd",
                "limits": {
                    "max_users": config["max_users"],
                    "max_customers": config["max_customers"],
                    "max_messages_per_month": config["max_messages_per_month"],
                    "max_ai_calls_per_month": config["max_ai_calls_per_month"],
                },
                "is_free": config["price_monthly"] == 0,
            }
            for plan_id, config in PLANS.items()
        ]
    }


@router.post("/checkout/{plan}")
async def create_checkout(
    plan: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    tenant: Annotated[Tenant, Depends(get_current_tenant_from_user)],
) -> dict:
    """Create a Stripe checkout session to upgrade plan."""
    if plan not in PLANS:
        raise HTTPException(status_code=400, detail=f"Invalid plan: {plan}")

    if PLANS[plan]["price_monthly"] == 0:
        raise HTTPException(status_code=400, detail="Cannot checkout free plan.")

    base_url = str(request.base_url).rstrip("/")
    service = StripeService()

    checkout_url = await service.create_checkout_session(
        tenant=tenant,
        plan=plan,
        success_url=f"{base_url}/dashboard/billing?success=true",
        cancel_url=f"{base_url}/dashboard/billing?cancelled=true",
    )

    return {"checkout_url": checkout_url}


@router.post("/portal")
async def billing_portal(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    tenant: Annotated[Tenant, Depends(get_current_tenant_from_user)],
) -> dict:
    """Open Stripe billing portal to manage subscription."""
    base_url = str(request.base_url).rstrip("/")
    service = StripeService()

    portal_url = await service.create_billing_portal_session(
        tenant=tenant,
        return_url=f"{base_url}/dashboard/billing",
    )

    return {"portal_url": portal_url}


@router.get("/usage")
async def get_usage(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    tenant: Annotated[Tenant, Depends(get_current_tenant_from_user)],
) -> dict:
    """Get current month usage and limits for the tenant."""
    tracker = UsageTracker(session, tenant)
    usage = await tracker.get_usage_percentage()
    return {
        "success": True,
        "data": usage,
        "tenant_plan": tenant.plan,
    }


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    stripe_signature: str = Header(alias="stripe-signature", default=""),
) -> SuccessResponse:
    """Handle incoming Stripe webhook events."""
    payload = await request.body()
    service = StripeService()

    result = await service.handle_webhook(
        payload=payload,
        signature=stripe_signature,
        session=session,
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    await session.commit()
    return SuccessResponse(message="Webhook processed.")
