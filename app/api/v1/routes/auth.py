from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.core.database.base import get_db
from app.models.auth import User
from app.schemas.auth import (
    EmailVerificationRequest,
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserCreate,
    UserPasswordChange,
    UserResponse,
)
from app.schemas.common import SuccessResponse
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(
    data: UserCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    service = AuthService(session)
    user = await service.register(data)
    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
async def login(
    data: LoginRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    service = AuthService(session)
    device_info = request.headers.get("user-agent")
    ip_address = request.client.host if request.client else None
    return await service.login(data, device_info=device_info, ip_address=ip_address)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    data: RefreshTokenRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    service = AuthService(session)
    return await service.refresh_tokens(data.refresh_token)


@router.post("/logout", response_model=SuccessResponse)
async def logout(
    data: RefreshTokenRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SuccessResponse:
    service = AuthService(session)
    await service.logout(data.refresh_token)
    return SuccessResponse(message="Logged out successfully.")


@router.post("/logout-all", response_model=SuccessResponse)
async def logout_all(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SuccessResponse:
    service = AuthService(session)
    await service.logout_all(current_user.id)
    return SuccessResponse(message="All sessions terminated.")


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.put("/me", response_model=UserResponse)
async def update_me(
    data: dict,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    from app.schemas.auth import UserUpdate
    service = AuthService(session)
    user = await service.update_user(current_user.id, UserUpdate(**data))
    return UserResponse.model_validate(user)


@router.post("/change-password", response_model=SuccessResponse)
async def change_password(
    data: UserPasswordChange,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SuccessResponse:
    service = AuthService(session)
    await service.change_password(current_user.id, data)
    return SuccessResponse(message="Password changed successfully.")


@router.post("/password-reset/request", response_model=SuccessResponse)
async def request_password_reset(
    data: PasswordResetRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SuccessResponse:
    service = AuthService(session)
    await service.request_password_reset(data.email)
    # Always return success to prevent user enumeration
    return SuccessResponse(message="If the email exists, a reset link has been sent.")


@router.post("/password-reset/confirm", response_model=SuccessResponse)
async def confirm_password_reset(
    data: PasswordResetConfirm,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SuccessResponse:
    service = AuthService(session)
    await service.confirm_password_reset(data)
    return SuccessResponse(message="Password reset successfully.")


@router.post("/verify-email", response_model=SuccessResponse)
async def verify_email(
    data: EmailVerificationRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SuccessResponse:
    service = AuthService(session)
    await service.verify_email(data.token)
    return SuccessResponse(message="Email verified successfully.")


@router.post("/send-verification", response_model=SuccessResponse)
async def resend_verification(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SuccessResponse:
    service = AuthService(session)
    await service.send_verification_email(current_user.id)
    return SuccessResponse(message="Verification email sent.")
