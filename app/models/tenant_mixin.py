"""
TenantMixin — add this to every model that needs tenant isolation.

Usage:
    class Customer(TenantMixin, BaseModel):
        __tablename__ = "customers"
        # ... rest of model

This automatically adds:
- tenant_id column with foreign key to tenants
- tenant relationship
- tenant_id index for query performance
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, declared_attr, relationship

if TYPE_CHECKING:
    from app.models.tenant import Tenant


class TenantMixin:
    """Mixin that adds tenant_id to any SQLAlchemy model."""

    @declared_attr
    def tenant_id(cls) -> Mapped[uuid.UUID]:
        return mapped_column(
            UUID(as_uuid=True),
            ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )

    @declared_attr
    def tenant(cls) -> Mapped["Tenant"]:
        return relationship("Tenant", lazy="select", foreign_keys=[cls.tenant_id])
