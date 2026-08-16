"""
Updated auth dependencies — resolve tenant from JWT token.
Replace/update app/auth/dependencies.py with these additions.
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.base import get_db
from app.core.logging import get_logger
from app.core.security import decode_token
from app.models.auth import User
from app.models.tenant import Tenant

logger = get_logger(__name__)
# auto_error=False so a missing Authorization header falls through to our own
# check below and raises 401 (unauthenticated), not FastAPI's default 403
# (which technically means "authenticated but forbidden" — wrong here).
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Get current user from JWT token and set tenant in request state."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise credentials_exception
    try:
        payload = decode_token(credentials.credentials)
        user_id: str = payload.get("sub")
        token_type: str = payload.get("type")

        if not user_id or token_type != "access":
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    user = await session.get(User, uuid.UUID(user_id))
    if not user or not user.is_active:
        raise credentials_exception

    return user


async def get_current_tenant_from_user(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Tenant:
    """
    Get the tenant for the currently logged in user.
    This is the most reliable way to resolve tenant in authenticated routes.
    """
    if not current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no tenant assigned.",
        )
    tenant = await session.get(Tenant, current_user.tenant_id)
    if not tenant or not tenant.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant is inactive or not found.",
        )
    return tenant


async def require_superuser(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Require the current user to be a superuser."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser access required.",
        )
    return current_user
