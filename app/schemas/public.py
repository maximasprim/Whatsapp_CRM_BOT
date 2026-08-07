from __future__ import annotations

import uuid

from pydantic import BaseModel, EmailStr, Field, field_validator


class PublicLeadRequest(BaseModel):
    """
    Submitted by the public marketing website (not an authenticated CRM
    user) when a visitor opts in to being contacted, or when they submit
    the Contact / Apply forms directly. Kept deliberately small — the site
    should never ask a visitor for more than a name and a phone number.
    """

    full_name: str = Field(..., min_length=2, max_length=150)
    phone: str = Field(..., min_length=7, max_length=30)
    email: EmailStr | None = None

    # Where on the site this came from, e.g. "calculator", "contact",
    # "apply". Free-form but short — used for the lead title/description,
    # not validated against an enum so the site can add pages without a
    # backend change.
    source_page: str = Field(..., max_length=100)

    # What caused the prompt/submission, e.g. "site_time_10min",
    # "calculator_time_5min", "calculator_interaction", "contact_submit",
    # "apply_submit".
    trigger: str = Field(..., max_length=100)

    product_interest: str | None = Field(None, max_length=150)
    message: str | None = Field(None, max_length=2000)

    # Honeypot field: real visitors never fill this in (it's hidden via
    # CSS on the site). If it arrives non-empty, treat as a bot and no-op.
    hp: str | None = Field(None, max_length=200)

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, v: str) -> str:
        cleaned = "".join(ch for ch in v if ch.isdigit() or ch == "+")
        if len(cleaned) < 7:
            raise ValueError("Enter a valid phone number.")
        return cleaned


class PublicLeadResponse(BaseModel):
    success: bool
    customer_id: uuid.UUID | None = None
    lead_id: uuid.UUID | None = None
