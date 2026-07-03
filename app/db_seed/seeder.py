from __future__ import annotations

import asyncio
import os
import sys

# ── Register ALL models first before any queries run ─────────────────────────
# SQLAlchemy resolves string-based relationships (e.g. "Customer" in Lead)
# lazily at first query time. Every model must be imported here so they are
# all registered before any repository or session code executes.
from app.models.company import Company                                       # noqa: F401
from app.models.customer import Customer                                     # noqa: F401
from app.models.lead import Lead, LeadStage                                  # noqa: F401
from app.models.product import Product                                       # noqa: F401
from app.models.order import Order, OrderItem, Payment                      # noqa: F401
from app.models.appointment import Appointment                               # noqa: F401
from app.models.task import Task                                             # noqa: F401
from app.models.followup import FollowUp                                     # noqa: F401
from app.models.note import Note                                             # noqa: F401
from app.models.campaign import Campaign, CampaignRecipient                 # noqa: F401
from app.models.ticket import SupportTicket, TicketMessage                  # noqa: F401
from app.models.tag import Tag                                               # noqa: F401
from app.models.activity import Activity                                     # noqa: F401
from app.models.notification import Notification                             # noqa: F401
from app.models.conversation import Conversation, ConversationMessage       # noqa: F401
from app.models.whatsapp_template import WhatsAppTemplate                   # noqa: F401
from app.models.conversation_summary import ConversationSummary             # noqa: F401
from app.models.knowledge_document import KnowledgeDocument, DocumentChunk  # noqa: F401
from app.models.calendar_credential import CalendarCredential               # noqa: F401
# ─────────────────────────────────────────────────────────────────────────────

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database.base import AsyncSessionLocal
from app.core.logging import get_logger, setup_logging
from app.core.security import hash_password
from app.db_seed.lead_stages_data import DEFAULT_LEAD_STAGES
from app.db_seed.permissions_data import generate_permission_catalogue
from app.db_seed.roles_data import DEFAULT_ROLES
from app.db_seed.whatsapp_templates_data import DEFAULT_WHATSAPP_TEMPLATES
from app.models.auth import Permission, Role, User
from app.repositories.auth import PermissionRepository, RoleRepository, UserRepository

logger = get_logger(__name__)


async def seed_permissions(session: AsyncSession) -> dict[str, Permission]:
    repo = PermissionRepository(session)
    catalogue = generate_permission_catalogue()
    created = 0
    permission_map: dict[str, Permission] = {}

    for perm_data in catalogue:
        existing = await repo.get_by_codename(perm_data["codename"])
        if existing:
            permission_map[perm_data["codename"]] = existing
            continue
        perm = await repo.create(**perm_data)
        permission_map[perm_data["codename"]] = perm
        created += 1

    logger.info("Permissions seeded", created=created, total=len(catalogue))
    return permission_map


async def seed_roles(session: AsyncSession, permission_map: dict[str, Permission]) -> dict[str, Role]:
    role_repo = RoleRepository(session)
    role_map: dict[str, Role] = {}
    created = 0

    for role_name, role_config in DEFAULT_ROLES.items():
        existing = await role_repo.get_by_name(role_name)
        if existing:
            role_map[role_name] = existing
            continue

        role = await role_repo.create(
            name=role_name,
            description=role_config["description"],
            is_system=role_config.get("is_system", False),
        )

        granted_codenames: set[str] = set()
        if role_config.get("resources") == "*":
            granted_codenames = set(permission_map.keys())
        elif "resources" in role_config:
            for resource in role_config["resources"]:
                granted_codenames.add(f"{resource}_manage")
                for action in ("create", "read", "update", "delete"):
                    granted_codenames.add(f"{resource}_{action}")
        elif "resources_partial" in role_config:
            for resource, actions in role_config["resources_partial"].items():
                for action in actions:
                    granted_codenames.add(f"{resource}_{action}")

        role.permissions = [
            permission_map[codename] for codename in granted_codenames if codename in permission_map
        ]
        session.add(role)
        await session.flush()

        role_map[role_name] = role
        created += 1

    logger.info("Roles seeded", created=created, total=len(DEFAULT_ROLES))
    return role_map


async def seed_lead_stages(session: AsyncSession) -> None:
    from sqlalchemy import select
    created = 0
    for stage_data in DEFAULT_LEAD_STAGES:
        stmt = select(LeadStage).where(LeadStage.name == stage_data["name"])
        result = await session.execute(stmt)
        if result.scalars().first():
            continue
        stage = LeadStage(**stage_data)
        session.add(stage)
        created += 1
    await session.flush()
    logger.info("Lead stages seeded", created=created, total=len(DEFAULT_LEAD_STAGES))


async def seed_whatsapp_templates(session: AsyncSession) -> None:
    from sqlalchemy import select
    created = 0
    for tmpl_data in DEFAULT_WHATSAPP_TEMPLATES:
        stmt = select(WhatsAppTemplate).where(WhatsAppTemplate.name == tmpl_data["name"])
        result = await session.execute(stmt)
        if result.scalars().first():
            continue
        tmpl = WhatsAppTemplate(**tmpl_data)
        session.add(tmpl)
        created += 1
    await session.flush()
    logger.info("WhatsApp templates seeded", created=created, total=len(DEFAULT_WHATSAPP_TEMPLATES))


async def seed_superuser(session: AsyncSession, role_map: dict[str, Role]) -> User | None:
    email = os.getenv("SEED_SUPERUSER_EMAIL", "admin@example.com")
    password = os.getenv("SEED_SUPERUSER_PASSWORD", "")

    if not password:
        logger.warning(
            "SEED_SUPERUSER_PASSWORD not set — skipping superuser creation. "
            "Set this env var to seed an initial admin account."
        )
        return None

    user_repo = UserRepository(session)
    existing = await user_repo.get_by_email(email)
    if existing:
        logger.info("Superuser already exists", email=email)
        return existing

    user = await user_repo.create(
        email=email.lower(),
        username=os.getenv("SEED_SUPERUSER_USERNAME", "admin"),
        hashed_password=hash_password(password),
        first_name=os.getenv("SEED_SUPERUSER_FIRST_NAME", "System"),
        last_name=os.getenv("SEED_SUPERUSER_LAST_NAME", "Administrator"),
        is_active=True,
        is_verified=True,
        is_superuser=True,
    )
    if "admin" in role_map:
        user.roles = [role_map["admin"]]
        session.add(user)
        await session.flush()

    logger.info("Superuser created", email=email)
    return user


async def run_seed() -> None:
    setup_logging()
    logger.info("Starting database seed", env=settings.APP_ENV)

    async with AsyncSessionLocal() as session:
        try:
            permission_map = await seed_permissions(session)
            role_map = await seed_roles(session, permission_map)
            await seed_lead_stages(session)
            await seed_whatsapp_templates(session)
            await seed_superuser(session, role_map)

            await session.commit()
            logger.info("Database seed completed successfully")
        except Exception as exc:
            await session.rollback()
            logger.error("Database seed failed", error=str(exc))
            raise


def main() -> None:
    asyncio.run(run_seed())
async def seed_roles(session: AsyncSession, permission_map: dict[str, Permission]) -> dict[str, Role]:
    role_repo = RoleRepository(session)
    role_map: dict[str, Role] = {}
    created = 0

    for role_name, role_config in DEFAULT_ROLES.items():
        existing = await role_repo.get_by_name(role_name)
        if existing:
            role_map[role_name] = existing
            continue

        # Create the role first without touching permissions
        role = Role(
            name=role_name,
            description=role_config["description"],
            is_system=role_config.get("is_system", False),
        )
        session.add(role)
        await session.flush()  # flush so role.id is assigned

        # Resolve which permission codenames this role gets
        granted_codenames: set[str] = set()
        if role_config.get("resources") == "*":
            granted_codenames = set(permission_map.keys())
        elif "resources" in role_config:
            for resource in role_config["resources"]:
                granted_codenames.add(f"{resource}_manage")
                for action in ("create", "read", "update", "delete"):
                    granted_codenames.add(f"{resource}_{action}")
        elif "resources_partial" in role_config:
            for resource, actions in role_config["resources_partial"].items():
                for action in actions:
                    granted_codenames.add(f"{resource}_{action}")

        # Insert into the junction table directly — avoids lazy load entirely
        from app.models.auth import role_permissions
        for codename in granted_codenames:
            if codename in permission_map:
                await session.execute(
                    role_permissions.insert().values(
                        role_id=role.id,
                        permission_id=permission_map[codename].id,
                    )
                )

        await session.flush()
        role_map[role_name] = role
        created += 1

    logger.info("Roles seeded", created=created, total=len(DEFAULT_ROLES))
    return role_map

if __name__ == "__main__":
    main()