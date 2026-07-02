from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Sequence

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.auth import Permission, RefreshToken, Role, User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(User, session)

    async def get_by_email(self, email: str) -> User | None:
        stmt = (
            select(User)
            .where(User.email == email.lower())
            .options(selectinload(User.roles).selectinload(Role.permissions))
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_username(self, username: str) -> User | None:
        stmt = select(User).where(User.username == username)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_with_roles(self, user_id: uuid.UUID) -> User | None:
        stmt = (
            select(User)
            .where(User.id == user_id)
            .options(selectinload(User.roles).selectinload(Role.permissions))
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def update_last_login(self, user_id: uuid.UUID) -> None:
        user = await self.get_by_id_or_raise(user_id)
        user.last_login_at = datetime.now(UTC)
        self.session.add(user)
        await self.session.flush()

    async def search(self, query: str, offset: int = 0, limit: int = 20) -> Sequence[User]:
        pattern = f"%{query}%"
        stmt = (
            select(User)
            .where(
                (User.email.ilike(pattern))
                | (User.username.ilike(pattern))
                | (User.first_name.ilike(pattern))
                | (User.last_name.ilike(pattern))
            )
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()


class RoleRepository(BaseRepository[Role]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Role, session)

    async def get_by_name(self, name: str) -> Role | None:
        stmt = select(Role).where(Role.name == name).options(selectinload(Role.permissions))
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_with_permissions(self, role_id: uuid.UUID) -> Role | None:
        stmt = (
            select(Role)
            .where(Role.id == role_id)
            .options(selectinload(Role.permissions))
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()


class PermissionRepository(BaseRepository[Permission]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Permission, session)

    async def get_by_codename(self, codename: str) -> Permission | None:
        return await self.get_by_field("codename", codename)

    async def get_by_resource(self, resource: str) -> Sequence[Permission]:
        stmt = select(Permission).where(Permission.resource == resource)
        result = await self.session.execute(stmt)
        return result.scalars().all()


class RefreshTokenRepository(BaseRepository[RefreshToken]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(RefreshToken, session)

    def _hash_token(self, token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    async def get_by_token(self, token: str) -> RefreshToken | None:
        token_hash = self._hash_token(token)
        stmt = (
            select(RefreshToken)
            .where(
                and_(
                    RefreshToken.token_hash == token_hash,
                    RefreshToken.revoked_at.is_(None),
                )
            )
            .options(selectinload(RefreshToken.user))
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def create_token(
        self,
        user_id: uuid.UUID,
        token: str,
        expires_at: datetime,
        device_info: str | None = None,
        ip_address: str | None = None,
    ) -> RefreshToken:
        return await self.create(
            user_id=user_id,
            token_hash=self._hash_token(token),
            expires_at=expires_at,
            device_info=device_info,
            ip_address=ip_address,
        )

    async def revoke_token(self, token: str) -> None:
        rt = await self.get_by_token(token)
        if rt:
            rt.revoked_at = datetime.now(UTC)
            self.session.add(rt)
            await self.session.flush()

    async def revoke_all_user_tokens(self, user_id: uuid.UUID) -> None:
        from sqlalchemy import update
        stmt = (
            select(RefreshToken)
            .where(
                and_(
                    RefreshToken.user_id == user_id,
                    RefreshToken.revoked_at.is_(None),
                )
            )
        )
        result = await self.session.execute(stmt)
        tokens = result.scalars().all()
        for token in tokens:
            token.revoked_at = datetime.now(UTC)
        await self.session.flush()
