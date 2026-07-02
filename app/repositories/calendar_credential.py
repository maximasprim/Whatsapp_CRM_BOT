from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_value, encrypt_value
from app.models.calendar_credential import CalendarCredential
from app.repositories.base import BaseRepository


class CalendarCredentialRepository(BaseRepository[CalendarCredential]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(CalendarCredential, session)

    async def get_by_user(self, user_id: uuid.UUID) -> CalendarCredential | None:
        stmt = select(CalendarCredential).where(
            CalendarCredential.user_id == user_id,
            CalendarCredential.is_active == True,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def store_tokens(
        self,
        user_id: uuid.UUID,
        access_token: str,
        refresh_token: str,
        expires_in: int,
        scope: str | None = None,
        calendar_id: str = "primary",
    ) -> CalendarCredential:
        from datetime import timedelta
        expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)

        existing = await self.get_by_user(user_id)
        if existing:
            existing.access_token_encrypted = encrypt_value(access_token)
            if refresh_token:  # Google only sends refresh_token on first consent
                existing.refresh_token_encrypted = encrypt_value(refresh_token)
            existing.token_expires_at = expires_at
            existing.scope = scope
            existing.is_active = True
            self.session.add(existing)
            await self.session.flush()
            return existing

        return await self.create(
            user_id=user_id,
            access_token_encrypted=encrypt_value(access_token),
            refresh_token_encrypted=encrypt_value(refresh_token),
            token_expires_at=expires_at,
            scope=scope,
            calendar_id=calendar_id,
        )

    async def get_decrypted_tokens(self, user_id: uuid.UUID) -> dict | None:
        cred = await self.get_by_user(user_id)
        if not cred:
            return None
        return {
            "access_token": decrypt_value(cred.access_token_encrypted),
            "refresh_token": decrypt_value(cred.refresh_token_encrypted),
            "expires_at": cred.token_expires_at,
            "calendar_id": cred.calendar_id,
            "is_expired": cred.token_expires_at.replace(tzinfo=UTC) <= datetime.now(UTC),
        }

    async def update_access_token(self, user_id: uuid.UUID, access_token: str, expires_in: int) -> None:
        from datetime import timedelta
        cred = await self.get_by_user(user_id)
        if cred:
            cred.access_token_encrypted = encrypt_value(access_token)
            cred.token_expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)
            self.session.add(cred)
            await self.session.flush()

    async def revoke(self, user_id: uuid.UUID) -> None:
        cred = await self.get_by_user(user_id)
        if cred:
            cred.is_active = False
            self.session.add(cred)
            await self.session.flush()
