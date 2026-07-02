from __future__ import annotations

import asyncio
import os
import uuid
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

# Force test environment values before importing app modules
os.environ.setdefault("APP_SECRET_KEY", "test-secret-key-for-tests-only-32chars")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-for-tests-32chars")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
os.environ.setdefault("AI_PROVIDER", "openai")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-key")
os.environ.setdefault("WHATSAPP_WEBHOOK_VERIFY_TOKEN", "test-verify-token")
os.environ.setdefault("WHATSAPP_APP_SECRET", "test-app-secret")

from app.core.database.base import Base, get_db
from app.models.auth import User
from app.core.security import hash_password, create_access_token

# Use an in-memory SQLite database for fast, isolated test runs.
# Note: a small number of Postgres-specific features (JSONB, native UUID,
# server-side enum types) are approximated by SQLAlchemy's SQLite compatibility
# layer; full-fidelity tests against Postgres should run in CI via the
# docker-compose test profile (see tests/integration/README).
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(bind=db_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    from app.main import app

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        email="testuser@example.com",
        username="testuser",
        hashed_password=hash_password("TestPassword123"),
        first_name="Test",
        last_name="User",
        is_active=True,
        is_verified=True,
        is_superuser=False,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def superuser(db_session: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        email="admin@example.com",
        username="admin",
        hashed_password=hash_password("AdminPassword123"),
        first_name="Admin",
        last_name="User",
        is_active=True,
        is_verified=True,
        is_superuser=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user: User) -> dict[str, str]:
    token = create_access_token(subject=test_user.id, extra_claims={"email": test_user.email})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def superuser_auth_headers(superuser: User) -> dict[str, str]:
    token = create_access_token(subject=superuser.id, extra_claims={"email": superuser.email, "is_superuser": True})
    return {"Authorization": f"Bearer {token}"}
