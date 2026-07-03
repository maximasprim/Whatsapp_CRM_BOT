from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.config import settings
from app.core.database.redis import RedisManager
from app.core.logging import setup_logging
from app.core.middleware import (
    RequestIDMiddleware,
    SecurityHeadersMiddleware,
    register_exception_handlers,
)

# Configure structured logging
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup / shutdown lifecycle."""
    from app.core.logging import get_logger
    logger = get_logger(__name__)

    # Startup
    logger.info("Starting WhatsApp CRM API", provider=settings.AI_PROVIDER, env=settings.APP_ENV)
    await RedisManager.connect()

    # Ensure upload directory exists
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    yield

    # Shutdown
    logger.info("Shutting down WhatsApp CRM API")
    await RedisManager.disconnect()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version="1.0.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # ── Rate Limiter ──────────────────────────────────────────────────────────
    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Custom middleware (order matters — outermost first) ───────────────────
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestIDMiddleware)

    # ── Exception handlers ────────────────────────────────────────────────────
    register_exception_handlers(app)

    # ── Routers ───────────────────────────────────────────────────────────────
    _register_routers(app)

    return app


def _register_routers(app: FastAPI) -> None:
    from app.api.v1.routes.auth import router as auth_router
    from app.api.v1.routes.users import router as users_router
    from app.api.v1.routes.customers import router as customers_router
    from app.api.v1.routes.companies import router as companies_router
    from app.api.v1.routes.leads import router as leads_router
    from app.api.v1.routes.products import router as products_router
    from app.api.v1.routes.orders import router as orders_router
    from app.api.v1.routes.appointments import router as appointments_router
    from app.api.v1.routes.tasks import router as tasks_router
    from app.api.v1.routes.campaigns import router as campaigns_router
    from app.api.v1.routes.tickets import router as tickets_router
    from app.api.v1.routes.analytics import router as analytics_router
    from app.api.v1.routes.whatsapp import router as whatsapp_router
    from app.api.v1.routes.ai_chat import router as ai_chat_router
    from app.api.v1.routes.knowledge_base import router as kb_router
    from app.api.v1.routes.notifications import router as notif_router
    from app.api.v1.routes.webhooks import router as webhook_router
    from app.api.v1.routes.ws_chat import router as ws_router
    from app.api.v1.routes.conversations import router as conversations_router
    from app.api.v1.routes.rag import router as rag_router
    from app.api.v1.routes.calendar import router as calendar_router

    prefix = "/api"
    app.include_router(auth_router, prefix=prefix)
    app.include_router(users_router, prefix=prefix)
    app.include_router(customers_router, prefix=prefix)
    app.include_router(companies_router, prefix=prefix)
    app.include_router(leads_router, prefix=prefix)
    app.include_router(products_router, prefix=prefix)
    app.include_router(orders_router, prefix=prefix)
    app.include_router(appointments_router, prefix=prefix)
    app.include_router(tasks_router, prefix=prefix)
    app.include_router(campaigns_router, prefix=prefix)
    app.include_router(tickets_router, prefix=prefix)
    app.include_router(analytics_router, prefix=prefix)
    app.include_router(whatsapp_router, prefix=prefix)
    app.include_router(ai_chat_router, prefix=prefix)
    app.include_router(kb_router, prefix=prefix)
    app.include_router(notif_router, prefix=prefix)
    app.include_router(webhook_router, prefix=prefix)
    app.include_router(ws_router, prefix=prefix)
    app.include_router(conversations_router, prefix=prefix)
    app.include_router(rag_router, prefix=prefix)
    app.include_router(calendar_router, prefix=prefix)

    @app.get("/health", tags=["Health"])
    async def health_check() -> dict:
        return {"status": "healthy", "service": settings.APP_NAME, "env": settings.APP_ENV}


app = create_app()
