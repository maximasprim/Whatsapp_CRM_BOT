from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
    InvalidTokenException,
    NotFoundException,
    UnauthorizedException,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    create_verification_token,
    decode_token,
    decode_verification_token,
    hash_password,
    verify_password,
)
from app.models.auth import Permission, Role, User
from app.repositories.auth import (
    PermissionRepository,
    RefreshTokenRepository,
    RoleRepository,
    UserRepository,
)
from app.schemas.auth import (
    LoginRequest,
    PasswordResetConfirm,
    PermissionCreate,
    RoleCreate,
    RoleUpdate,
    TokenResponse,
    UserCreate,
    UserPasswordChange,
    UserUpdate,
)


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.user_repo = UserRepository(session)
        self.role_repo = RoleRepository(session)
        self.perm_repo = PermissionRepository(session)
        self.token_repo = RefreshTokenRepository(session)

    # ── Registration ──────────────────────────────────────────────────────────
    async def register(self, data: UserCreate) -> User:
        if await self.user_repo.get_by_email(data.email):
            raise ConflictException("Email already registered.")
        if await self.user_repo.get_by_username(data.username):
            raise ConflictException("Username already taken.")

        roles: list[Role] = []
        for role_id in data.role_ids:
            role = await self.role_repo.get_by_id(role_id)
            if role:
                roles.append(role)

        user = await self.user_repo.create(
            email=data.email.lower(),
            username=data.username,
            hashed_password=hash_password(data.password),
            first_name=data.first_name,
            last_name=data.last_name,
            phone=data.phone,
        )
        user.roles = roles
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    # ── Login ─────────────────────────────────────────────────────────────────
    async def login(
        self,
        data: LoginRequest,
        device_info: str | None = None,
        ip_address: str | None = None,
    ) -> TokenResponse:
        user = await self.user_repo.get_by_email(data.email)
        if not user or not verify_password(data.password, user.hashed_password):
            raise UnauthorizedException("Invalid email or password.")
        if not user.is_active:
            raise ForbiddenException("Account is disabled.")

        access_token = create_access_token(
            subject=user.id,
            extra_claims={"email": user.email, "is_superuser": user.is_superuser},
        )
        refresh_token = create_refresh_token(subject=user.id)
        expires_at = datetime.now(UTC) + timedelta(
            days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
        )
        await self.token_repo.create_token(
            user_id=user.id,
            token=refresh_token,
            expires_at=expires_at,
            device_info=device_info,
            ip_address=ip_address,
        )
        await self.user_repo.update_last_login(user.id)

        from app.schemas.auth import UserResponse
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserResponse.model_validate(user),
        )

    # ── Token refresh ─────────────────────────────────────────────────────────
    async def refresh_tokens(self, refresh_token: str) -> TokenResponse:
        token_obj = await self.token_repo.get_by_token(refresh_token)
        if not token_obj:
            raise InvalidTokenException("Refresh token not found or already revoked.")
        if token_obj.expires_at.replace(tzinfo=UTC) < datetime.now(UTC):
            raise InvalidTokenException("Refresh token has expired.")

        payload = decode_token(refresh_token, expected_type="refresh")
        user = await self.user_repo.get_with_roles(token_obj.user_id)
        if not user or not user.is_active:
            raise UnauthorizedException("User not found or inactive.")

        await self.token_repo.revoke_token(refresh_token)
        new_access = create_access_token(
            subject=user.id,
            extra_claims={"email": user.email, "is_superuser": user.is_superuser},
        )
        new_refresh = create_refresh_token(subject=user.id)
        expires_at = datetime.now(UTC) + timedelta(
            days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
        )
        await self.token_repo.create_token(
            user_id=user.id,
            token=new_refresh,
            expires_at=expires_at,
        )
        from app.schemas.auth import UserResponse
        return TokenResponse(
            access_token=new_access,
            refresh_token=new_refresh,
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserResponse.model_validate(user),
        )

    # ── Logout ────────────────────────────────────────────────────────────────
    async def logout(self, refresh_token: str) -> None:
        await self.token_repo.revoke_token(refresh_token)

    async def logout_all(self, user_id: uuid.UUID) -> None:
        await self.token_repo.revoke_all_user_tokens(user_id)

    # ── Password management ───────────────────────────────────────────────────
    async def change_password(
        self, user_id: uuid.UUID, data: UserPasswordChange
    ) -> None:
        user = await self.user_repo.get_by_id_or_raise(user_id)
        if not verify_password(data.current_password, user.hashed_password):
            raise BadRequestException("Current password is incorrect.")
        user.hashed_password = hash_password(data.new_password)
        user.password_changed_at = datetime.now(UTC)
        self.session.add(user)
        await self.session.flush()

    async def request_password_reset(self, email: str) -> str:
        user = await self.user_repo.get_by_email(email)
        if not user:
            return ""  # Silently ignore for security
        token = create_verification_token(
            {"sub": str(user.id), "type": "password_reset"}, expires_hours=2
        )
        return token

    async def confirm_password_reset(self, data: PasswordResetConfirm) -> None:
        try:
            payload = decode_verification_token(data.token)
        except Exception as exc:
            raise BadRequestException("Invalid or expired reset token.") from exc

        if payload.get("type") != "password_reset":
            raise BadRequestException("Invalid reset token type.")

        user = await self.user_repo.get_by_id_or_raise(uuid.UUID(payload["sub"]))
        user.hashed_password = hash_password(data.new_password)
        user.password_changed_at = datetime.now(UTC)
        self.session.add(user)
        await self.token_repo.revoke_all_user_tokens(user.id)
        await self.session.flush()

    # ── Email verification ────────────────────────────────────────────────────
    async def send_verification_email(self, user_id: uuid.UUID) -> str:
        user = await self.user_repo.get_by_id_or_raise(user_id)
        if user.is_verified:
            raise BadRequestException("Email already verified.")
        return create_verification_token(
            {"sub": str(user.id), "type": "email_verify"}, expires_hours=24
        )

    async def verify_email(self, token: str) -> None:
        try:
            payload = decode_verification_token(token)
        except Exception as exc:
            raise BadRequestException("Invalid or expired verification token.") from exc
        if payload.get("type") != "email_verify":
            raise BadRequestException("Invalid verification token type.")
        user = await self.user_repo.get_by_id_or_raise(uuid.UUID(payload["sub"]))
        user.is_verified = True
        user.email_verified_at = datetime.now(UTC)
        self.session.add(user)
        await self.session.flush()

    # ── User management ───────────────────────────────────────────────────────
    async def update_user(self, user_id: uuid.UUID, data: UserUpdate) -> User:
        user = await self.user_repo.get_with_roles(user_id)
        if user is None:
            raise NotFoundException("User not found.")
        update_data = data.model_dump(exclude_unset=True, exclude={"role_ids"})
        for key, value in update_data.items():
            setattr(user, key, value)
        if data.role_ids is not None:
            roles = []
            for role_id in data.role_ids:
                role = await self.role_repo.get_by_id(role_id)
                if role:
                    roles.append(role)
            user.roles = roles
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    # ── Role management ───────────────────────────────────────────────────────
    async def create_role(self, data: RoleCreate) -> Role:
        if await self.role_repo.get_by_name(data.name):
            raise ConflictException(f"Role '{data.name}' already exists.")
        perms: list[Permission] = []
        for pid in data.permission_ids:
            perm = await self.perm_repo.get_by_id(pid)
            if perm:
                perms.append(perm)
        role = await self.role_repo.create(name=data.name, description=data.description)
        role.permissions = perms
        self.session.add(role)
        await self.session.flush()
        await self.session.refresh(role)
        return role

    async def create_permission(self, data: PermissionCreate) -> Permission:
        if await self.perm_repo.get_by_codename(data.codename):
            raise ConflictException(f"Permission '{data.codename}' already exists.")
        return await self.perm_repo.create(**data.model_dump())
