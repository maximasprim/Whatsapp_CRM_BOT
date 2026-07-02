from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.base import get_db
from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.core.security import decode_token
from app.models.auth import User
from app.repositories.auth import UserRepository

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    if not credentials:
        raise UnauthorizedException("No authentication token provided.")

    payload = decode_token(credentials.credentials, expected_type="access")
    user_id_str: str = payload.get("sub", "")
    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError as exc:
        raise UnauthorizedException("Invalid token subject.") from exc

    repo = UserRepository(session)
    user = await repo.get_with_roles(user_id)
    if not user:
        raise UnauthorizedException("User not found.")
    if not user.is_active:
        raise ForbiddenException("Account is disabled.")
    return user


async def get_current_active_verified_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if not current_user.is_verified:
        raise ForbiddenException("Email not verified. Please verify your email first.")
    return current_user


def require_permission(resource: str, action: str):
    """Factory that returns a dependency checking for a specific permission."""

    async def _check(
        user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if not user.has_permission(resource, action):
            raise ForbiddenException(
                f"Missing permission: {resource}:{action}"
            )
        return user

    return _check


def require_superuser(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    if not user.is_superuser:
        raise ForbiddenException("Superuser access required.")
    return user
