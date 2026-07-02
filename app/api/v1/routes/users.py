from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_superuser
from app.core.database.base import get_db
from app.models.auth import User
from app.repositories.auth import UserRepository
from app.schemas.auth import UserCreate, UserResponse, UserUpdate
from app.schemas.common import PaginatedResponse, SuccessResponse
from app.services.auth import AuthService

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("", response_model=PaginatedResponse[UserResponse])
async def list_users(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_superuser)],
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[UserResponse]:
    repo = UserRepository(session)
    offset = (page - 1) * page_size
    if search:
        items = await repo.search(search, offset=offset, limit=page_size)
        total = len(items)
    else:
        items = await repo.get_all(offset=offset, limit=page_size)
        total = await repo.count()
    return PaginatedResponse.create(
        data=[UserResponse.model_validate(u) for u in items],
        total=total, page=page, page_size=page_size,
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    repo = UserRepository(session)
    user = await repo.get_by_id_or_raise(user_id)
    return UserResponse.model_validate(user)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    data: UserUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    service = AuthService(session)
    user = await service.update_user(user_id, data)
    return UserResponse.model_validate(user)


@router.delete("/{user_id}", response_model=SuccessResponse)
async def delete_user(
    user_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_superuser)],
) -> SuccessResponse:
    repo = UserRepository(session)
    await repo.delete_by_id(user_id)
    return SuccessResponse(message="User deleted.")
