"""
BaseTenantRepository — base class for all tenant-aware repositories.
All CRM repositories extend this instead of writing tenant filtering
in every single method.
"""
from __future__ import annotations

import uuid
from typing import Any, Generic, Type, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.base import BaseModel

ModelType = TypeVar("ModelType", bound=BaseModel)


class BaseTenantRepository(Generic[ModelType]):
    """
    Base repository with automatic tenant filtering on all queries.
    
    Usage:
        class CustomerRepository(BaseTenantRepository[Customer]):
            model = Customer
            
        repo = CustomerRepository(session, tenant_id=tenant.id)
        customers = await repo.get_all()  # Only this tenant's customers
    """

    model: Type[ModelType]

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    def _base_query(self):
        """Base query always filtered by tenant."""
        return select(self.model).where(
            self.model.tenant_id == self.tenant_id
        )

    async def get_by_id(self, record_id: uuid.UUID) -> ModelType | None:
        result = await self.session.execute(
            self._base_query().where(self.model.id == record_id)
        )
        return result.scalars().first()

    async def get_by_id_or_raise(self, record_id: uuid.UUID) -> ModelType:
        from app.core.exceptions import NotFoundException
        obj = await self.get_by_id(record_id)
        if obj is None:
            raise NotFoundException(
                f"{self.model.__name__} with id '{record_id}' not found.",
                error_code=f"{self.model.__name__.upper()}_NOT_FOUND",
            )
        return obj

    async def get_all(
        self,
        page: int = 1,
        page_size: int = 20,
        order_by=None,
    ) -> tuple[list[ModelType], int]:
        stmt = self._base_query()
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        else:
            stmt = stmt.order_by(self.model.created_at.desc())

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()

        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def create(self, **kwargs: Any) -> ModelType:
        kwargs["tenant_id"] = self.tenant_id
        obj = self.model(**kwargs)
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def update(self, obj: ModelType, **kwargs: Any) -> ModelType:
        self._assert_tenant(obj)
        for key, value in kwargs.items():
            if value is not None or key in kwargs:
                setattr(obj, key, value)
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def delete(self, obj: ModelType) -> None:
        self._assert_tenant(obj)
        await self.session.delete(obj)
        await self.session.flush()

    async def delete_by_id(self, record_id: uuid.UUID) -> None:
        obj = await self.get_by_id_or_raise(record_id)
        await self.delete(obj)

    async def count(self) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(
                self._base_query().subquery()
            )
        )
        return result.scalar_one()

    def _assert_tenant(self, obj: ModelType) -> None:
        """Ensure the object belongs to the current tenant."""
        if getattr(obj, "tenant_id", None) != self.tenant_id:
            raise PermissionError(
                f"Object {obj.id} does not belong to tenant {self.tenant_id}"
            )
