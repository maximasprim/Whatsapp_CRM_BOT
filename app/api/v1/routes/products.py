from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_tenant_from_user, get_current_user
from app.core.database.base import get_db
from app.models.auth import User
from app.schemas.common import PaginatedResponse, SuccessResponse
from app.schemas.crm import ProductCreate, ProductResponse, ProductUpdate
from app.services.crm import ProductService

router = APIRouter(prefix="/products", tags=["Products"])


@router.post("", response_model=ProductResponse, status_code=201)
async def create_product(
    data: ProductCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ProductResponse:
    # SAAS CHANGE: Resolve tenant before constructing ProductService.
    tenant = await get_current_tenant_from_user(current_user, session)
    service = ProductService(session, tenant_id=tenant.id)

    return ProductResponse.model_validate(await service.create(data))


@router.get("", response_model=PaginatedResponse[ProductResponse])
async def list_products(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[ProductResponse]:
    # SAAS CHANGE: Tenant scopes product listing.
    tenant = await get_current_tenant_from_user(current_user, session)
    service = ProductService(session, tenant_id=tenant.id)

    items, total = await service.list(
        search=search,
        offset=(page - 1) * page_size,
        limit=page_size,
    )
    return PaginatedResponse.create(
        data=[ProductResponse.model_validate(p) for p in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ProductResponse:
    # SAAS CHANGE: Resolve tenant before retrieving the product.
    tenant = await get_current_tenant_from_user(current_user, session)
    service = ProductService(session, tenant_id=tenant.id)

    return ProductResponse.model_validate(await service.get(product_id))


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: uuid.UUID,
    data: ProductUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ProductResponse:
    # SAAS CHANGE: Resolve tenant before updating the product.
    tenant = await get_current_tenant_from_user(current_user, session)
    service = ProductService(session, tenant_id=tenant.id)

    return ProductResponse.model_validate(await service.update(product_id, data))


@router.delete("/{product_id}", response_model=SuccessResponse)
async def delete_product(
    product_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SuccessResponse:
    # SAAS CHANGE: Resolve tenant before deleting the product.
    tenant = await get_current_tenant_from_user(current_user, session)
    service = ProductService(session, tenant_id=tenant.id)

    await service.delete(product_id)
    return SuccessResponse(message="Product deleted.")
