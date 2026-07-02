from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.core.database.base import get_db
from app.models.auth import User
from app.models.customer import Customer, CustomerStatus
from app.models.lead import Lead, LeadStatus
from app.models.order import Order
from app.models.conversation import Conversation
from app.models.ticket import SupportTicket

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/dashboard")
async def dashboard_stats(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    now = datetime.now(UTC)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    total_customers = (await session.execute(select(func.count(Customer.id)))).scalar_one()
    active_customers = (await session.execute(select(func.count(Customer.id)).where(Customer.status == CustomerStatus.ACTIVE))).scalar_one()
    new_customers_month = (await session.execute(select(func.count(Customer.id)).where(Customer.created_at >= month_start))).scalar_one()

    total_leads = (await session.execute(select(func.count(Lead.id)))).scalar_one()
    open_leads = (await session.execute(select(func.count(Lead.id)).where(Lead.status.notin_([LeadStatus.WON, LeadStatus.LOST, LeadStatus.DISQUALIFIED])))).scalar_one()
    won_leads = (await session.execute(select(func.count(Lead.id)).where(Lead.status == LeadStatus.WON))).scalar_one()

    total_revenue = (await session.execute(select(func.sum(Order.total_amount)))).scalar_one() or 0.0
    monthly_revenue = (await session.execute(select(func.sum(Order.total_amount)).where(Order.created_at >= month_start))).scalar_one() or 0.0

    open_conversations = (await session.execute(select(func.count(Conversation.id)).where(Conversation.status == "open"))).scalar_one()
    open_tickets = (await session.execute(select(func.count(SupportTicket.id)).where(SupportTicket.status == "open"))).scalar_one()

    return {
        "customers": {
            "total": total_customers,
            "active": active_customers,
            "new_this_month": new_customers_month,
        },
        "leads": {
            "total": total_leads,
            "open": open_leads,
            "won": won_leads,
            "conversion_rate": round((won_leads / total_leads * 100) if total_leads else 0, 2),
        },
        "revenue": {
            "total": round(total_revenue, 2),
            "this_month": round(monthly_revenue, 2),
        },
        "conversations": {"open": open_conversations},
        "tickets": {"open": open_tickets},
        "generated_at": now.isoformat(),
    }


@router.get("/leads/funnel")
async def lead_funnel(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    result = await session.execute(
        select(Lead.status, func.count(Lead.id), func.sum(Lead.estimated_value)).group_by(Lead.status)
    )
    rows = result.all()
    return {
        "funnel": [
            {"status": row[0], "count": row[1], "value": float(row[2] or 0)}
            for row in rows
        ]
    }


@router.get("/customers/growth")
async def customer_growth(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    days: int = Query(30, ge=7, le=365),
) -> dict:
    since = datetime.now(UTC) - timedelta(days=days)
    result = await session.execute(
        select(
            func.date_trunc("day", Customer.created_at).label("day"),
            func.count(Customer.id).label("count"),
        )
        .where(Customer.created_at >= since)
        .group_by(func.date_trunc("day", Customer.created_at))
        .order_by(func.date_trunc("day", Customer.created_at))
    )
    rows = result.all()
    return {
        "growth": [{"date": str(row.day.date()), "count": row.count} for row in rows]
    }
