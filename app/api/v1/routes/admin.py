"""
Admin routes — superuser-only panel to manage all tenants.
Add to app/api/v1/routes/admin.py
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_superuser
from app.core.database.base import get_db
from app.core.logging import get_logger
from app.models.auth import User
from app.models.billing import UsageRecord
from app.models.conversation import Conversation
from app.models.customer import Customer
from app.models.tenant import Tenant
from app.schemas.common import PaginatedResponse, SuccessResponse
from app.tenant.repository import TenantRepository
from app.schemas.tenant import TenantResponse

logger = get_logger(__name__)
router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/dashboard")
async def admin_dashboard(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_superuser)],
) -> dict:
    """Admin dashboard — overview of all tenants and platform stats."""

    # Total tenants
    total_tenants = (
        await session.execute(select(func.count()).select_from(Tenant))
    ).scalar_one()

    # Active tenants
    active_tenants = (
        await session.execute(
            select(func.count()).select_from(Tenant).where(Tenant.is_active == True)
        )
    ).scalar_one()

    # Total customers across all tenants
    total_customers = (
        await session.execute(select(func.count()).select_from(Customer))
    ).scalar_one()

    # Total conversations across all tenants
    total_conversations = (
        await session.execute(select(func.count()).select_from(Conversation))
    ).scalar_one()

    # Plans breakdown
    plans_result = await session.execute(
        select(Tenant.plan, func.count(Tenant.id))
        .group_by(Tenant.plan)
    )
    plans_breakdown = {row[0]: row[1] for row in plans_result.all()}

    return {
        "success": True,
        "data": {
            "total_tenants": total_tenants,
            "active_tenants": active_tenants,
            "inactive_tenants": total_tenants - active_tenants,
            "total_customers": total_customers,
            "total_conversations": total_conversations,
            "plans_breakdown": plans_breakdown,
        },
    }


@router.get("/tenants")
async def list_tenants(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_superuser)],
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    plan: str | None = None,
    is_active: bool | None = None,
) -> dict:
    """List all tenants with filters."""
    stmt = select(Tenant)

    if search:
        from sqlalchemy import or_
        stmt = stmt.where(
            or_(
                Tenant.name.ilike(f"%{search}%"),
                Tenant.slug.ilike(f"%{search}%"),
                Tenant.domain.ilike(f"%{search}%"),
            )
        )
    if plan:
        stmt = stmt.where(Tenant.plan == plan)
    if is_active is not None:
        stmt = stmt.where(Tenant.is_active == is_active)

    stmt = stmt.order_by(Tenant.created_at.desc())
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await session.execute(stmt)
    tenants = result.scalars().all()

    return {
        "success": True,
        "data": [TenantResponse.model_validate(t) for t in tenants],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/tenants/{tenant_id}")
async def get_tenant_detail(
    tenant_id: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_superuser)],
) -> dict:
    """Get detailed info about a specific tenant."""
    tenant = await session.get(Tenant, uuid.UUID(tenant_id))
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found.")

    # Customer count for this tenant
    customer_count = (
        await session.execute(
            select(func.count()).select_from(Customer).where(
                Customer.tenant_id == tenant.id
            )
        )
    ).scalar_one()

    # Conversation count
    conv_count = (
        await session.execute(
            select(func.count()).select_from(Conversation).where(
                Conversation.tenant_id == tenant.id
            )
        )
    ).scalar_one()

    # Usage this month
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    usage_result = await session.execute(
        select(UsageRecord).where(
            UsageRecord.tenant_id == tenant.id,
            UsageRecord.year == now.year,
            UsageRecord.month == now.month,
        )
    )
    usage = usage_result.scalars().first()

    return {
        "success": True,
        "data": {
            "tenant": TenantResponse.model_validate(tenant),
            "stats": {
                "customer_count": customer_count,
                "conversation_count": conv_count,
                "this_month": {
                    "messages_sent": usage.messages_sent if usage else 0,
                    "ai_calls": usage.ai_calls if usage else 0,
                } if usage else {},
            },
        },
    }


@router.put("/tenants/{tenant_id}/activate")
async def toggle_tenant_active(
    tenant_id: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_superuser)],
) -> SuccessResponse:
    """Activate or deactivate a tenant."""
    tenant = await session.get(Tenant, uuid.UUID(tenant_id))
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found.")

    tenant.is_active = not tenant.is_active
    await session.commit()

    action = "activated" if tenant.is_active else "deactivated"
    logger.info(f"Tenant {action}", tenant_slug=tenant.slug, by=current_user.email)
    return SuccessResponse(message=f"Tenant {action}.")


@router.put("/tenants/{tenant_id}/plan")
async def change_tenant_plan(
    tenant_id: str,
    plan: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_superuser)],
) -> SuccessResponse:
    """Manually change a tenant's plan (admin override)."""
    from app.billing.stripe_service import PLANS

    tenant = await session.get(Tenant, uuid.UUID(tenant_id))
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found.")

    if plan not in PLANS:
        raise HTTPException(status_code=400, detail=f"Invalid plan: {plan}")

    plan_config = PLANS[plan]
    tenant.plan = plan
    tenant.max_users = plan_config["max_users"]
    tenant.max_customers = plan_config["max_customers"]
    tenant.max_messages_per_month = plan_config["max_messages_per_month"]
    tenant.max_ai_calls_per_month = plan_config["max_ai_calls_per_month"]

    await session.commit()
    logger.info(
        "Tenant plan changed by admin",
        tenant_slug=tenant.slug,
        new_plan=plan,
        by=current_user.email,
    )
    return SuccessResponse(message=f"Tenant plan changed to {plan}.")


@router.get("/usage")
async def platform_usage(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_superuser)],
) -> dict:
    """Platform-wide usage stats across all tenants."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    result = await session.execute(
        select(UsageRecord).where(
            UsageRecord.year == now.year,
            UsageRecord.month == now.month,
        )
    )
    records = result.scalars().all()

    total_messages = sum(r.messages_sent for r in records)
    total_ai_calls = sum(r.ai_calls for r in records)
    total_received = sum(r.messages_received for r in records)

    return {
        "success": True,
        "data": {
            "period": f"{now.year}-{now.month:02d}",
            "total_messages_sent": total_messages,
            "total_messages_received": total_received,
            "total_ai_calls": total_ai_calls,
            "active_tenants_this_month": len(records),
        },
    }
