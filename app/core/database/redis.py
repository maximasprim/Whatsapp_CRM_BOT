from __future__ import annotations

import json
from typing import Any

import redis.asyncio as aioredis
from redis.asyncio import Redis

from app.core.config import settings


class RedisManager:
    """Manages Redis connections for sessions, cache, and pub/sub."""

    _main: Redis | None = None
    _session: Redis | None = None
    _cache: Redis | None = None

    @classmethod
    async def connect(cls) -> None:
        cls._main = aioredis.from_url(
            settings.REDIS_URL, encoding="utf-8", decode_responses=True
        )
        cls._session = aioredis.from_url(
            settings.REDIS_URL.rsplit("/", 1)[0] + f"/{settings.REDIS_SESSION_DB}",
            encoding="utf-8",
            decode_responses=True,
        )
        cls._cache = aioredis.from_url(
            settings.REDIS_URL.rsplit("/", 1)[0] + f"/{settings.REDIS_CACHE_DB}",
            encoding="utf-8",
            decode_responses=True,
        )

    @classmethod
    async def disconnect(cls) -> None:
        for conn in (cls._main, cls._session, cls._cache):
            if conn:
                await conn.aclose()

    @classmethod
    def main(cls) -> Redis:
        if not cls._main:
            raise RuntimeError("Redis not connected. Call RedisManager.connect() first.")
        return cls._main

    @classmethod
    def session(cls) -> Redis:
        if not cls._session:
            raise RuntimeError("Redis not connected. Call RedisManager.connect() first.")
        return cls._session

    @classmethod
    def cache(cls) -> Redis:
        if not cls._cache:
            raise RuntimeError("Redis not connected. Call RedisManager.connect() first.")
        return cls._cache


# ── Helpers ───────────────────────────────────────────────────────────────────

async def set_cache(key: str, value: Any, ttl: int = 300) -> None:
    await RedisManager.cache().setex(key, ttl, json.dumps(value, default=str))


async def get_cache(key: str) -> Any | None:
    data = await RedisManager.cache().get(key)
    return json.loads(data) if data else None


async def delete_cache(key: str) -> None:
    await RedisManager.cache().delete(key)


async def set_session_data(session_id: str, data: dict[str, Any], ttl: int = 3600) -> None:
    await RedisManager.session().setex(session_id, ttl, json.dumps(data, default=str))


async def get_session_data(session_id: str) -> dict[str, Any] | None:
    data = await RedisManager.session().get(session_id)
    return json.loads(data) if data else None


async def delete_session_data(session_id: str) -> None:
    await RedisManager.session().delete(session_id)


async def get_redis() -> Redis:
    return RedisManager.main()
