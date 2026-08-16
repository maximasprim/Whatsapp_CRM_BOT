from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import Tenant


class TenantRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, tenant_id: uuid.UUID) -> Tenant | None:
        return await self.session.get(Tenant, tenant_id)

    async def get_by_slug(self, slug: str) -> Tenant | None:
        result = await self.session.execute(
            select(Tenant).where(Tenant.slug == slug)
        )
        return result.scalars().first()

    async def get_by_domain(self, domain: str) -> Tenant | None:
        result = await self.session.execute(
            select(Tenant).where(Tenant.domain == domain)
        )
        return result.scalars().first()

    async def get_all(self, page: int = 1, page_size: int = 20) -> tuple[list[Tenant], int]:
        from sqlalchemy import func
        count_result = await self.session.execute(
            select(func.count()).select_from(Tenant)
        )
        total = count_result.scalar_one()

        result = await self.session.execute(
            select(Tenant)
            .order_by(Tenant.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def create(self, **kwargs) -> Tenant:
        tenant = Tenant(**kwargs)
        self.session.add(tenant)
        await self.session.flush()
        await self.session.refresh(tenant)
        return tenant

    async def update(self, tenant: Tenant, **kwargs) -> Tenant:
        for key, value in kwargs.items():
            if value is not None:
                setattr(tenant, key, value)
        self.session.add(tenant)
        await self.session.flush()
        await self.session.refresh(tenant)
        return tenant

    async def slug_exists(self, slug: str) -> bool:
        result = await self.session.execute(
            select(Tenant).where(Tenant.slug == slug)
        )
        return result.scalars().first() is not None

    async def domain_exists(self, domain: str) -> bool:
        result = await self.session.execute(
            select(Tenant).where(Tenant.domain == domain)
        )
        return result.scalars().first() is not None
