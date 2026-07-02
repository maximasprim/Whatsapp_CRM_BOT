from __future__ import annotations

import uuid
from typing import Any, Generic, Sequence, Type, TypeVar

from sqlalchemy import Select, asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.base import BaseModel
from app.core.exceptions import NotFoundException

ModelT = TypeVar("ModelT", bound=BaseModel)


class BaseRepository(Generic[ModelT]):
    """Generic async repository providing common CRUD operations."""

    def __init__(self, model: Type[ModelT], session: AsyncSession) -> None:
        self.model = model
        self.session = session

    async def get_by_id(self, id: uuid.UUID) -> ModelT | None:
        result = await self.session.get(self.model, id)
        return result

    async def get_by_id_or_raise(self, id: uuid.UUID) -> ModelT:
        obj = await self.get_by_id(id)
        if obj is None:
            raise NotFoundException(
                f"{self.model.__name__} with id '{id}' not found.",
                error_code=f"{self.model.__name__.upper()}_NOT_FOUND",
            )
        return obj

    async def get_all(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        order_by: str | None = None,
        order_dir: str = "asc",
    ) -> Sequence[ModelT]:
        stmt = select(self.model)
        stmt = self._apply_ordering(stmt, order_by, order_dir)
        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count(self) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(self.model)
        )
        return result.scalar_one()

    async def create(self, **kwargs: Any) -> ModelT:
        obj = self.model(**kwargs)
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def update(self, obj: ModelT, **kwargs: Any) -> ModelT:
        for key, value in kwargs.items():
            if hasattr(obj, key):
                setattr(obj, key, value)
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def delete(self, obj: ModelT) -> None:
        await self.session.delete(obj)
        await self.session.flush()

    async def delete_by_id(self, id: uuid.UUID) -> None:
        obj = await self.get_by_id_or_raise(id)
        await self.delete(obj)

    async def exists(self, **filters: Any) -> bool:
        stmt = select(func.count()).select_from(self.model)
        for key, value in filters.items():
            stmt = stmt.where(getattr(self.model, key) == value)
        result = await self.session.execute(stmt)
        return (result.scalar_one() or 0) > 0

    async def get_by_field(self, field: str, value: Any) -> ModelT | None:
        stmt = select(self.model).where(getattr(self.model, field) == value)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    def _apply_ordering(
        self, stmt: Select, order_by: str | None, order_dir: str
    ) -> Select:
        if order_by and hasattr(self.model, order_by):
            col = getattr(self.model, order_by)
            stmt = stmt.order_by(asc(col) if order_dir == "asc" else desc(col))
        elif hasattr(self.model, "created_at"):
            stmt = stmt.order_by(desc(self.model.created_at))
        return stmt
