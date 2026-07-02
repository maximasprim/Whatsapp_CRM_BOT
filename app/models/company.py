from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import Enum as SAEnum, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import BaseModel

if TYPE_CHECKING:
    from app.models.customer import Customer


class CompanySize(str, enum.Enum):
    MICRO = "micro"          # 1-9
    SMALL = "small"          # 10-49
    MEDIUM = "medium"        # 50-249
    LARGE = "large"          # 250-999
    ENTERPRISE = "enterprise" # 1000+


class Company(BaseModel):
    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    size: Mapped[CompanySize | None] = mapped_column(
        SAEnum(CompanySize, name="companysize", values_callable=lambda x: [e.value for e in x]), nullable=True
    )
    employee_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    annual_revenue: Mapped[float | None] = mapped_column(Float, nullable=True)

    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(255), nullable=True)

    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    assigned_to: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    custom_fields: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    customers: Mapped[list["Customer"]] = relationship("Customer", back_populates="company")

    __table_args__ = (Index("ix_companies_name_industry", "name", "industry"),)
