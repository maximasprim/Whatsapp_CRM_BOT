from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_tenant_from_user, get_current_user
from app.core.database.base import get_db
from app.models.auth import User
from app.schemas.common import PaginatedResponse
from app.schemas.crm import CampaignCreate, CampaignResponse
from app.services.crm import CampaignService

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])


@router.post("", response_model=CampaignResponse, status_code=201)
async def create_campaign(
    data: CampaignCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CampaignResponse:
    # SAAS CHANGE: Resolve tenant before constructing CampaignService.
    tenant = await get_current_tenant_from_user(current_user, session)
    service = CampaignService(session, tenant_id=tenant.id)

    return CampaignResponse.model_validate(
        await service.create(data, created_by=current_user.id)
    )


@router.get("", response_model=PaginatedResponse[CampaignResponse])
async def list_campaigns(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> PaginatedResponse[CampaignResponse]:
    # SAAS CHANGE: Tenant scopes campaign listing.
    tenant = await get_current_tenant_from_user(current_user, session)
    service = CampaignService(session, tenant_id=tenant.id)

    items, total = await service.list()
    return PaginatedResponse.create(
        data=[CampaignResponse.model_validate(c) for c in items],
        total=total,
        page=1,
        page_size=20,
    )


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CampaignResponse:
    # SAAS CHANGE: Tenant scopes campaign retrieval.
    tenant = await get_current_tenant_from_user(current_user, session)
    service = CampaignService(session, tenant_id=tenant.id)

    return CampaignResponse.model_validate(await service.get(campaign_id))
