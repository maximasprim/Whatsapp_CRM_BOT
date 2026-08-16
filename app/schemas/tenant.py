from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


# ── Request schemas ───────────────────────────────────────────────────────────

class TenantCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    slug: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-z0-9-]+$")
    domain: str | None = None
    business_description: str | None = None
    website: str | None = None
    country: str | None = None
    timezone: str = "UTC"
    primary_color: str | None = "#f97316"
    plan: str = "starter"

    @field_validator("slug")
    @classmethod
    def slug_lowercase(cls, v: str) -> str:
        return v.lower().strip()


class TenantUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=255)
    domain: str | None = None
    logo_url: str | None = None
    primary_color: str | None = None
    business_description: str | None = None
    website: str | None = None
    country: str | None = None
    timezone: str | None = None
    custom_settings: dict | None = None


class TenantWhatsAppConfig(BaseModel):
    whatsapp_phone_number_id: str
    whatsapp_access_token: str
    whatsapp_business_account_id: str
    whatsapp_webhook_verify_token: str
    whatsapp_app_secret: str | None = None
    whatsapp_phone_number: str | None = None


class TenantAIConfig(BaseModel):
    ai_provider: str = Field(..., pattern=r"^(openai|gemini)$")
    ai_api_key: str
    ai_model: str | None = None


class BusinessRegister(BaseModel):
    """Used when a new business signs up for the SaaS."""
    # Business info
    business_name: str = Field(..., min_length=2, max_length=255)
    business_slug: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-z0-9-]+$")
    business_description: str | None = None
    country: str | None = None
    timezone: str = "UTC"

    # Admin user info
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: str
    password: str = Field(..., min_length=8)
    phone: str | None = None

    @field_validator("business_slug")
    @classmethod
    def slug_lowercase(cls, v: str) -> str:
        return v.lower().strip()


# ── Response schemas ──────────────────────────────────────────────────────────

class TenantResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    domain: str | None
    logo_url: str | None
    primary_color: str | None
    business_description: str | None
    website: str | None
    country: str | None
    timezone: str
    is_active: bool
    plan: str
    max_users: int
    max_customers: int
    max_messages_per_month: int
    max_ai_calls_per_month: int
    ai_provider: str
    whatsapp_phone_number: str | None
    whatsapp_phone_number_id: str | None
    whatsapp_business_account_id: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TenantPublicResponse(BaseModel):
    """Safe public response — no sensitive credentials."""
    id: uuid.UUID
    name: str
    slug: str
    logo_url: str | None
    primary_color: str | None
    business_description: str | None
    timezone: str
    plan: str

    model_config = {"from_attributes": True}


class BusinessRegisterResponse(BaseModel):
    tenant: TenantResponse
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
