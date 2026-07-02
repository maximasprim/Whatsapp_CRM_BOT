from __future__ import annotations
import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.dependencies import get_current_user
from app.core.database.base import get_db
from app.models.auth import User
from app.schemas.common import PaginatedResponse, SuccessResponse
from app.schemas.crm import CompanyCreate, CompanyResponse, CompanyUpdate
from app.services.crm import CompanyService

router = APIRouter(prefix="/companies", tags=["Companies"])

@router.post("", response_model=CompanyResponse, status_code=201)
async def create_company(data: CompanyCreate, session: Annotated[AsyncSession, Depends(get_db)], current_user: Annotated[User, Depends(get_current_user)]) -> CompanyResponse:
    return CompanyResponse.model_validate(await CompanyService(session).create(data))

@router.get("", response_model=PaginatedResponse[CompanyResponse])
async def list_companies(session: Annotated[AsyncSession, Depends(get_db)], current_user: Annotated[User, Depends(get_current_user)], search: str | None = Query(None), page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)) -> PaginatedResponse[CompanyResponse]:
    items, total = await CompanyService(session).list(search=search, offset=(page-1)*page_size, limit=page_size)
    return PaginatedResponse.create(data=[CompanyResponse.model_validate(c) for c in items], total=total, page=page, page_size=page_size)

@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(company_id: uuid.UUID, session: Annotated[AsyncSession, Depends(get_db)], current_user: Annotated[User, Depends(get_current_user)]) -> CompanyResponse:
    return CompanyResponse.model_validate(await CompanyService(session).get(company_id))

@router.put("/{company_id}", response_model=CompanyResponse)
async def update_company(company_id: uuid.UUID, data: CompanyUpdate, session: Annotated[AsyncSession, Depends(get_db)], current_user: Annotated[User, Depends(get_current_user)]) -> CompanyResponse:
    return CompanyResponse.model_validate(await CompanyService(session).update(company_id, data))

@router.delete("/{company_id}", response_model=SuccessResponse)
async def delete_company(company_id: uuid.UUID, session: Annotated[AsyncSession, Depends(get_db)], current_user: Annotated[User, Depends(get_current_user)]) -> SuccessResponse:
    await CompanyService(session).delete(company_id)
    return SuccessResponse(message="Company deleted.")
