from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_tenant_from_user, get_current_user, require_superuser
from app.core.database.base import get_db
from app.core.logging import get_logger
from app.core.security import hash_password, create_access_token, create_refresh_token
from app.models.auth import User
from app.models.tenant import Tenant
from app.repositories.auth import RoleRepository, UserRepository
from app.schemas.common import PaginatedResponse, SuccessResponse
from app.tenant.repository import TenantRepository
from app.schemas.tenant import (
    BusinessRegister,
    BusinessRegisterResponse,
    TenantAIConfig,
    TenantCreate,
    TenantResponse,
    TenantUpdate,
    TenantWhatsAppConfig,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/tenants", tags=["Tenants"])


# ── Public — Business Registration ────────────────────────────────────────────

@router.post("/register", response_model=BusinessRegisterResponse, status_code=201)
async def register_business(
    data: BusinessRegister,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> BusinessRegisterResponse:
    """Register a new business and create its admin user."""
    repo = TenantRepository(session)
    user_repo = UserRepository(session)
    role_repo = RoleRepository(session)

    # Check slug is available
    if await repo.slug_exists(data.business_slug):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This business slug is already taken. Please choose another.",
        )

    # Check email is available
    if await user_repo.get_by_email(data.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    # Create tenant
    tenant = await repo.create(
        name=data.business_name,
        slug=data.business_slug,
        business_description=data.business_description,
        country=data.country,
        timezone=data.timezone,
        plan="starter",
        is_active=True,
    )

    # Create admin user for this tenant
    admin_role = await role_repo.get_by_name("admin")
    user = await user_repo.create(
        tenant_id=tenant.id,
        email=data.email.lower(),
        username=f"{data.business_slug}_admin",
        hashed_password=hash_password(data.password),
        first_name=data.first_name,
        last_name=data.last_name,
        phone=data.phone,
        is_active=True,
        is_verified=True,
        is_superuser=False,
    )

    if admin_role:
        from app.models.auth import user_roles
        await session.execute(
            user_roles.insert().values(user_id=user.id, role_id=admin_role.id)
        )

    await session.commit()
    await session.refresh(tenant)
    await session.refresh(user)

    # Generate tokens
    access_token = create_access_token(
        subject=str(user.id),
        tenant_id=str(tenant.id),
        extra_claims={
            "email": user.email,
            "is_superuser": False,
        },
    )
    refresh_token = create_refresh_token(subject=str(user.id))

    logger.info(
        "New business registered",
        tenant_slug=tenant.slug,
        user_email=user.email,
    )

    return BusinessRegisterResponse(
        tenant=TenantResponse.model_validate(tenant),
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=1800,
    )


# ── Tenant settings (admin of that tenant) ────────────────────────────────────

@router.get("/me", response_model=TenantResponse)
async def get_my_tenant(
    current_tenant: Annotated[Tenant, Depends(get_current_tenant_from_user)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TenantResponse:
    """Get the current tenant's information."""
    return TenantResponse.model_validate(current_tenant)


@router.put("/me", response_model=TenantResponse)
async def update_my_tenant(
    data: TenantUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_tenant: Annotated[Tenant, Depends(get_current_tenant_from_user)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TenantResponse:
    """Update tenant profile and branding."""
    repo = TenantRepository(session)
    tenant = await repo.update(
        current_tenant,
        **data.model_dump(exclude_unset=True),
    )
    await session.commit()
    return TenantResponse.model_validate(tenant)


@router.put("/me/whatsapp", response_model=TenantResponse)
async def configure_whatsapp(
    data: TenantWhatsAppConfig,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_tenant: Annotated[Tenant, Depends(get_current_tenant_from_user)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TenantResponse:
    """Configure WhatsApp credentials for this tenant."""
    repo = TenantRepository(session)
    tenant = await repo.update(
        current_tenant,
        whatsapp_phone_number_id=data.whatsapp_phone_number_id,
        whatsapp_access_token=data.whatsapp_access_token,
        whatsapp_business_account_id=data.whatsapp_business_account_id,
        whatsapp_webhook_verify_token=data.whatsapp_webhook_verify_token,
        whatsapp_app_secret=data.whatsapp_app_secret,
        whatsapp_phone_number=data.whatsapp_phone_number,
    )
    await session.commit()
    logger.info("WhatsApp configured", tenant_slug=tenant.slug)
    return TenantResponse.model_validate(tenant)


@router.put("/me/ai", response_model=TenantResponse)
async def configure_ai(
    data: TenantAIConfig,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_tenant: Annotated[Tenant, Depends(get_current_tenant_from_user)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TenantResponse:
    """Configure AI provider for this tenant."""
    repo = TenantRepository(session)
    tenant = await repo.update(
        current_tenant,
        ai_provider=data.ai_provider,
        ai_api_key=data.ai_api_key,
        ai_model=data.ai_model,
    )
    await session.commit()
    return TenantResponse.model_validate(tenant)


@router.get("/me/webhook-url")
async def get_webhook_url(
    current_tenant: Annotated[Tenant, Depends(get_current_tenant_from_user)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Get the WhatsApp webhook URL for this tenant to register in Meta."""
    base_url = "https://saidika-crm.onrender.com"
    return {
        "webhook_url": f"{base_url}/api/whatsapp/webhook/{current_tenant.slug}",
        "verify_token": current_tenant.whatsapp_webhook_verify_token or "not configured",
        "instructions": "Register this URL in Meta → WhatsApp → Configuration → Webhook",
    }


# ── Superuser only — manage all tenants ───────────────────────────────────────

@router.get("", response_model=PaginatedResponse)
async def list_all_tenants(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_superuser)],
    page: int = 1,
    page_size: int = 20,
) -> PaginatedResponse:
    """List all tenants — superuser only."""
    repo = TenantRepository(session)
    tenants, total = await repo.get_all(page=page, page_size=page_size)
    return PaginatedResponse(
        data=[TenantResponse.model_validate(t) for t in tenants],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.post("", response_model=TenantResponse, status_code=201)
async def create_tenant(
    data: TenantCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_superuser)],
) -> TenantResponse:
    """Create a new tenant — superuser only."""
    repo = TenantRepository(session)

    if await repo.slug_exists(data.slug):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Slug already exists.",
        )

    tenant = await repo.create(**data.model_dump())
    await session.commit()
    return TenantResponse.model_validate(tenant)


@router.put("/{tenant_id}/activate", response_model=SuccessResponse)
async def activate_tenant(
    tenant_id: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_superuser)],
) -> SuccessResponse:
    """Activate or deactivate a tenant — superuser only."""
    import uuid as _uuid
    repo = TenantRepository(session)
    tenant = await repo.get_by_id(_uuid.UUID(tenant_id))
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found.")
    tenant.is_active = not tenant.is_active
    await session.commit()
    status_str = "activated" if tenant.is_active else "deactivated"
    return SuccessResponse(message=f"Tenant {status_str}.")

# from __future__ import annotations

# from typing import Annotated

# from fastapi import APIRouter, Depends, HTTPException, status
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.auth.dependencies import get_current_user, require_superuser
# from app.auth.dependencies import get_current_tenant_from_user, get_current_user, require_superuser
# from app.core.database.base import get_db
# from app.core.logging import get_logger
# from app.core.security import hash_password, create_access_token, create_refresh_token
# from app.models.auth import User
# from app.models.tenant import Tenant
# from app.repositories.auth import RoleRepository, UserRepository
# from app.schemas.common import PaginatedResponse, SuccessResponse
# from app.tenant.middleware import get_current_tenant
# from app.tenant.repository import TenantRepository
# from app.schemas.tenant import (
#     BusinessRegister,
#     BusinessRegisterResponse,
#     TenantAIConfig,
#     TenantCreate,
#     TenantResponse,
#     TenantUpdate,
#     TenantWhatsAppConfig,
# )

# logger = get_logger(__name__)
# router = APIRouter(prefix="/tenants", tags=["Tenants"])


# # ── Public — Business Registration ────────────────────────────────────────────

# @router.post("/register", response_model=BusinessRegisterResponse, status_code=201)
# async def register_business(
#     data: BusinessRegister,
#     session: Annotated[AsyncSession, Depends(get_db)],
# ) -> BusinessRegisterResponse:
#     """Register a new business and create its admin user."""
#     repo = TenantRepository(session)
#     user_repo = UserRepository(session)
#     role_repo = RoleRepository(session)

#     # Check slug is available
#     if await repo.slug_exists(data.business_slug):
#         raise HTTPException(
#             status_code=status.HTTP_409_CONFLICT,
#             detail="This business slug is already taken. Please choose another.",
#         )

#     # Check email is available
#     if await user_repo.get_by_email(data.email):
#         raise HTTPException(
#             status_code=status.HTTP_409_CONFLICT,
#             detail="An account with this email already exists.",
#         )

#     # Create tenant
#     tenant = await repo.create(
#         name=data.business_name,
#         slug=data.business_slug,
#         business_description=data.business_description,
#         country=data.country,
#         timezone=data.timezone,
#         plan="starter",
#         is_active=True,
#     )

#     # Create admin user for this tenant
#     admin_role = await role_repo.get_by_name("admin")
#     user = await user_repo.create(
#         tenant_id=tenant.id,
#         email=data.email.lower(),
#         username=f"{data.business_slug}_admin",
#         hashed_password=hash_password(data.password),
#         first_name=data.first_name,
#         last_name=data.last_name,
#         phone=data.phone,
#         is_active=True,
#         is_verified=True,
#         is_superuser=False,
#     )

#     if admin_role:
#         from app.models.auth import user_roles
#         await session.execute(
#             user_roles.insert().values(user_id=user.id, role_id=admin_role.id)
#         )

#     await session.commit()
#     await session.refresh(tenant)
#     await session.refresh(user)

#     # Generate tokens
#     # access_token = create_access_token(
#     #     subject=str(user.id),
#     #     email=user.email,
#     #     tenant_id=str(tenant.id),
#     #     is_superuser=False,
#     # )
#     access_token = create_access_token(
#     subject=str(user.id),
#     tenant_id=str(tenant.id),
#     extra_claims={
#         "email": user.email,
#         "is_superuser": False,
#     },
# )
#     refresh_token = create_refresh_token(subject=str(user.id))

#     logger.info(
#         "New business registered",
#         tenant_slug=tenant.slug,
#         user_email=user.email,
#     )

#     return BusinessRegisterResponse(
#         tenant=TenantResponse.model_validate(tenant),
#         access_token=access_token,
#         refresh_token=refresh_token,
#         expires_in=1800,
#     )


# # ── Tenant settings (admin of that tenant) ────────────────────────────────────

# @router.get("/me", response_model=TenantResponse)
# async def get_my_tenant(
#     current_tenant: Annotated[Tenant, Depends(get_current_tenant)],
#     current_user: Annotated[User, Depends(get_current_user)],
# ) -> TenantResponse:
#     """Get the current tenant's information."""
#     return TenantResponse.model_validate(current_tenant)


# @router.put("/me", response_model=TenantResponse)
# async def update_my_tenant(
#     data: TenantUpdate,
#     session: Annotated[AsyncSession, Depends(get_db)],
#     current_tenant: Annotated[Tenant, Depends(get_current_tenant)],
#     current_user: Annotated[User, Depends(get_current_user)],
# ) -> TenantResponse:
#     """Update tenant profile and branding."""
#     repo = TenantRepository(session)
#     tenant = await repo.update(
#         current_tenant,
#         **data.model_dump(exclude_unset=True),
#     )
#     await session.commit()
#     return TenantResponse.model_validate(tenant)


# @router.put("/me/whatsapp", response_model=TenantResponse)
# async def configure_whatsapp(
#     data: TenantWhatsAppConfig,
#     session: Annotated[AsyncSession, Depends(get_db)],
#     current_tenant: Annotated[Tenant, Depends(get_current_tenant)],
#     current_user: Annotated[User, Depends(get_current_user)],
# ) -> TenantResponse:
#     """Configure WhatsApp credentials for this tenant."""
#     repo = TenantRepository(session)
#     tenant = await repo.update(
#         current_tenant,
#         whatsapp_phone_number_id=data.whatsapp_phone_number_id,
#         whatsapp_access_token=data.whatsapp_access_token,
#         whatsapp_business_account_id=data.whatsapp_business_account_id,
#         whatsapp_webhook_verify_token=data.whatsapp_webhook_verify_token,
#         whatsapp_app_secret=data.whatsapp_app_secret,
#         whatsapp_phone_number=data.whatsapp_phone_number,
#     )
#     await session.commit()
#     logger.info("WhatsApp configured", tenant_slug=tenant.slug)
#     return TenantResponse.model_validate(tenant)


# @router.put("/me/ai", response_model=TenantResponse)
# async def configure_ai(
#     data: TenantAIConfig,
#     session: Annotated[AsyncSession, Depends(get_db)],
#     current_tenant: Annotated[Tenant, Depends(get_current_tenant)],
#     current_user: Annotated[User, Depends(get_current_user)],
# ) -> TenantResponse:
#     """Configure AI provider for this tenant."""
#     repo = TenantRepository(session)
#     tenant = await repo.update(
#         current_tenant,
#         ai_provider=data.ai_provider,
#         ai_api_key=data.ai_api_key,
#         ai_model=data.ai_model,
#     )
#     await session.commit()
#     return TenantResponse.model_validate(tenant)


# @router.get("/me/webhook-url")
# async def get_webhook_url(
#     # request: Annotated[object, Depends(lambda r: r)],
#     current_tenant: Annotated[Tenant, Depends(get_current_tenant)],
#     current_user: Annotated[User, Depends(get_current_user)],
# ) -> dict:
#     """Get the WhatsApp webhook URL for this tenant to register in Meta."""
#     base_url = "https://saidika-crm.onrender.com"
#     return {
#         "webhook_url": f"{base_url}/api/whatsapp/webhook/{current_tenant.slug}",
#         "verify_token": current_tenant.whatsapp_webhook_verify_token or "not configured",
#         "instructions": "Register this URL in Meta → WhatsApp → Configuration → Webhook",
#     }


# # ── Superuser only — manage all tenants ───────────────────────────────────────

# @router.get("", response_model=PaginatedResponse)
# async def list_all_tenants(
#     session: Annotated[AsyncSession, Depends(get_db)],
#     current_user: Annotated[User, Depends(require_superuser)],
#     page: int = 1,
#     page_size: int = 20,
# ) -> PaginatedResponse:
#     """List all tenants — superuser only."""
#     repo = TenantRepository(session)
#     tenants, total = await repo.get_all(page=page, page_size=page_size)
#     return PaginatedResponse(
#         data=[TenantResponse.model_validate(t) for t in tenants],
#         total=total,
#         page=page,
#         page_size=page_size,
#         total_pages=(total + page_size - 1) // page_size,
#     )


# @router.post("", response_model=TenantResponse, status_code=201)
# async def create_tenant(
#     data: TenantCreate,
#     session: Annotated[AsyncSession, Depends(get_db)],
#     current_user: Annotated[User, Depends(require_superuser)],
# ) -> TenantResponse:
#     """Create a new tenant — superuser only."""
#     repo = TenantRepository(session)

#     if await repo.slug_exists(data.slug):
#         raise HTTPException(
#             status_code=status.HTTP_409_CONFLICT,
#             detail="Slug already exists.",
#         )

#     tenant = await repo.create(**data.model_dump())
#     await session.commit()
#     return TenantResponse.model_validate(tenant)


# @router.put("/{tenant_id}/activate", response_model=SuccessResponse)
# async def activate_tenant(
#     tenant_id: str,
#     session: Annotated[AsyncSession, Depends(get_db)],
#     current_user: Annotated[User, Depends(require_superuser)],
# ) -> SuccessResponse:
#     """Activate or deactivate a tenant — superuser only."""
#     import uuid as _uuid
#     repo = TenantRepository(session)
#     tenant = await repo.get_by_id(_uuid.UUID(tenant_id))
#     if not tenant:
#         raise HTTPException(status_code=404, detail="Tenant not found.")
#     tenant.is_active = not tenant.is_active
#     await session.commit()
#     status_str = "activated" if tenant.is_active else "deactivated"
#     return SuccessResponse(message=f"Tenant {status_str}.")
