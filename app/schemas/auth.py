from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


# ── Permission schemas ────────────────────────────────────────────────────────
class PermissionBase(BaseModel):
    name: str = Field(..., max_length=100)
    codename: str = Field(..., max_length=100)
    description: str | None = None
    resource: str = Field(..., max_length=100)
    action: str = Field(..., max_length=50)


class PermissionCreate(PermissionBase):
    pass


class PermissionResponse(PermissionBase):
    id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Role schemas ──────────────────────────────────────────────────────────────
class RoleBase(BaseModel):
    name: str = Field(..., max_length=100)
    description: str | None = None


class RoleCreate(RoleBase):
    permission_ids: list[uuid.UUID] = []


class RoleUpdate(BaseModel):
    name: str | None = Field(None, max_length=100)
    description: str | None = None
    permission_ids: list[uuid.UUID] | None = None


class RoleResponse(RoleBase):
    id: uuid.UUID
    is_system: bool
    permissions: list[PermissionResponse] = []
    created_at: datetime

    model_config = {"from_attributes": True}


# ── User schemas ──────────────────────────────────────────────────────────────
class UserBase(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100)
    first_name: str = Field(..., max_length=100)
    last_name: str = Field(..., max_length=100)
    phone: str | None = Field(None, max_length=20)


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=128)
    confirm_password: str = Field(..., min_length=8, max_length=128)
    role_ids: list[uuid.UUID] = []

    @model_validator(mode="after")
    def passwords_match(self) -> "UserCreate":
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        return self

    @field_validator("password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit.")
        return v


class UserUpdate(BaseModel):
    first_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    phone: str | None = Field(None, max_length=20)
    avatar_url: str | None = None
    role_ids: list[uuid.UUID] | None = None


class UserResponse(UserBase):
    id: uuid.UUID
    is_active: bool
    is_verified: bool
    is_superuser: bool
    avatar_url: str | None
    last_login_at: datetime | None
    created_at: datetime
    roles: list[RoleResponse] = []

    model_config = {"from_attributes": True}


class UserPasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)
    confirm_password: str

    @model_validator(mode="after")
    def passwords_match(self) -> "UserPasswordChange":
        if self.new_password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        return self


# ── Auth schemas ──────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, max_length=128)
    confirm_password: str

    @model_validator(mode="after")
    def passwords_match(self) -> "PasswordResetConfirm":
        if self.new_password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        return self


class EmailVerificationRequest(BaseModel):
    token: str
