from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.get("/health")
async def webhook_health() -> dict:
    return {"status": "ok"}
