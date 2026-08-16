from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_tenant_from_user, get_current_user
from app.core.database.base import get_db
from app.models.auth import User
from app.schemas.common import PaginatedResponse, SuccessResponse
from app.schemas.crm import CustomerCreate, CustomerResponse, CustomerUpdate
from app.services.crm import CustomerService

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.post("", response_model=CustomerResponse, status_code=201)
async def create_customer(
    data: CustomerCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CustomerResponse:
    # SAAS CHANGE: Resolve the authenticated user's tenant before creating the service.
    tenant = await get_current_tenant_from_user(current_user, session)
    service = CustomerService(session, tenant_id=tenant.id)

    customer = await service.create(data, created_by=current_user.id)
    return CustomerResponse.model_validate(customer)


@router.get("", response_model=PaginatedResponse[CustomerResponse])
async def list_customers(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    search: str | None = Query(None),
    status: str | None = Query(None),
    assigned_to: uuid.UUID | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[CustomerResponse]:
    # SAAS CHANGE: Resolve tenant so all repository queries are tenant-scoped.
    tenant = await get_current_tenant_from_user(current_user, session)
    service = CustomerService(session, tenant_id=tenant.id)

    offset = (page - 1) * page_size
    items, total = await service.list(
        search=search,
        status=status,
        assigned_to=assigned_to,
        offset=offset,
        limit=page_size,
    )
    return PaginatedResponse.create(
        data=[CustomerResponse.model_validate(c) for c in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CustomerResponse:
    # SAAS CHANGE: Resolve tenant before accessing the customer service.
    tenant = await get_current_tenant_from_user(current_user, session)
    service = CustomerService(session, tenant_id=tenant.id)

    customer = await service.get(customer_id)
    return CustomerResponse.model_validate(customer)


@router.put("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: uuid.UUID,
    data: CustomerUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CustomerResponse:
    # SAAS CHANGE: Resolve tenant before updating the customer.
    tenant = await get_current_tenant_from_user(current_user, session)
    service = CustomerService(session, tenant_id=tenant.id)

    customer = await service.update(customer_id, data, updated_by=current_user.id)
    return CustomerResponse.model_validate(customer)


@router.delete("/{customer_id}", response_model=SuccessResponse)
async def delete_customer(
    customer_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SuccessResponse:
    # SAAS CHANGE: Resolve tenant before deleting the customer.
    tenant = await get_current_tenant_from_user(current_user, session)
    service = CustomerService(session, tenant_id=tenant.id)

    await service.delete(customer_id)
    return SuccessResponse(message="Customer deleted.")
