from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_tenant_from_user, get_current_user
from app.core.database.base import get_db
from app.models.auth import User
from app.schemas.crm import OrderCreate, OrderResponse
from app.services.crm import OrderService

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.post("", response_model=OrderResponse, status_code=201)
async def create_order(
    data: OrderCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> OrderResponse:
    # SAAS CHANGE: Resolve tenant before constructing OrderService.
    tenant = await get_current_tenant_from_user(current_user, session)
    service = OrderService(session, tenant_id=tenant.id)

    return OrderResponse.model_validate(
        await service.create(data, created_by=current_user.id)
    )


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> OrderResponse:
    # SAAS CHANGE: Resolve tenant before retrieving the order.
    tenant = await get_current_tenant_from_user(current_user, session)
    service = OrderService(session, tenant_id=tenant.id)

    return OrderResponse.model_validate(await service.get(order_id))
