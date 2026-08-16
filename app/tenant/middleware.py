from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.base import get_db
from app.core.logging import get_logger
from app.models.tenant import Tenant

logger = get_logger(__name__)

DEFAULT_TENANT_SLUG = "default"


async def get_tenant_from_request(
    request: Request,
    session: AsyncSession,
) -> Tenant:
    """
    Resolve the current tenant from the request.
    Resolution order:
    1. X-Tenant-Slug header (for API clients)
    2. Subdomain (acme.saidika-crm.com → slug = acme)
    3. Custom domain (app.acmebusiness.com → look up by domain)
    4. Fall back to default tenant
    """
    # ── Option 1: explicit header ─────────────────────────────────────────────
    tenant_slug = request.headers.get("X-Tenant-Slug")

    # ── Option 2: subdomain ───────────────────────────────────────────────────
    if not tenant_slug:
        host = request.headers.get("host", "")
        parts = host.split(".")
        # Only treat as subdomain if format is something.domain.tld
        if len(parts) >= 3 and parts[0] not in ("www", "api", "app"):
            tenant_slug = parts[0]

    # ── Option 3: custom domain ───────────────────────────────────────────────
    if not tenant_slug:
        host = request.headers.get("host", "").split(":")[0]
        result = await session.execute(
            select(Tenant).where(Tenant.domain == host, Tenant.is_active == True)
        )
        tenant = result.scalars().first()
        if tenant:
            return tenant

    # ── Option 4: default tenant ──────────────────────────────────────────────
    if not tenant_slug:
        tenant_slug = DEFAULT_TENANT_SLUG

    # Look up tenant by slug
    result = await session.execute(
        select(Tenant).where(
            Tenant.slug == tenant_slug,
            Tenant.is_active == True,
        )
    )
    tenant = result.scalars().first()

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant '{tenant_slug}' not found or inactive.",
        )

    return tenant


async def get_current_tenant(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Tenant:
    """FastAPI dependency — inject the current tenant into any route."""
    return await get_tenant_from_request(request, session)


async def get_tenant_from_jwt(request: Request) -> uuid.UUID | None:
    """
    Extract tenant_id from JWT token claims.
    Used as a fast path when the JWT already contains the tenant.
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    return uuid.UUID(tenant_id) if tenant_id else None
