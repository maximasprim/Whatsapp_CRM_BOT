from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.core.database.base import get_db
from app.models.auth import User
from app.schemas.common import PaginatedResponse, SuccessResponse
from app.schemas.crm import TaskCreate, TaskResponse, TaskUpdate
from app.services.crm import TaskService

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.post("", response_model=TaskResponse, status_code=201)
async def create_task(data: TaskCreate, session: Annotated[AsyncSession, Depends(get_db)], current_user: Annotated[User, Depends(get_current_user)]) -> TaskResponse:
    return TaskResponse.model_validate(await TaskService(session).create(data, created_by=current_user.id))


@router.get("", response_model=PaginatedResponse[TaskResponse])
async def list_tasks(session: Annotated[AsyncSession, Depends(get_db)], current_user: Annotated[User, Depends(get_current_user)], assigned_to: uuid.UUID | None = Query(None), page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)) -> PaginatedResponse[TaskResponse]:
    service = TaskService(session)
    offset = (page - 1) * page_size
    items, total = await service.list(assigned_to=assigned_to, offset=offset, limit=page_size)
    return PaginatedResponse.create(data=[TaskResponse.model_validate(t) for t in items], total=total, page=page, page_size=page_size)


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(task_id: uuid.UUID, data: TaskUpdate, session: Annotated[AsyncSession, Depends(get_db)], current_user: Annotated[User, Depends(get_current_user)]) -> TaskResponse:
    return TaskResponse.model_validate(await TaskService(session).update(task_id, data))


@router.delete("/{task_id}", response_model=SuccessResponse)
async def delete_task(task_id: uuid.UUID, session: Annotated[AsyncSession, Depends(get_db)], current_user: Annotated[User, Depends(get_current_user)]) -> SuccessResponse:
    await TaskService(session).delete(task_id)
    return SuccessResponse(message="Task deleted.")
