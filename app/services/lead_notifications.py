from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.auth import Role, User, user_roles
from app.models.notification import NotificationType
from app.services.crm import NotificationService
from app.websocket.connection_manager import manager
from app.websocket.events import WSEventType, build_event

logger = get_logger(__name__)

AGENT_ROLE_NAME = "sales_agent"


async def notify_agents_of_new_lead(
    session: AsyncSession,
    lead_id: uuid.UUID,
    lead_title: str,
    customer_name: str,
    customer_phone: str,
) -> None:
    """
    Notifies every active user holding the sales_agent role that a new,
    unassigned website lead needs attention: an in-app Notification row
    (so it shows up next time they open the CRM) plus a live push over the
    chat websocket (so it shows up immediately if they're online). Queries
    User/Role directly rather than via the Role.users relationship since
    that relationship isn't eager-loaded and would trigger a lazy load
    that fails under the async session.
    """
    stmt = (
        select(User)
        .join(user_roles, user_roles.c.user_id == User.id)
        .join(Role, Role.id == user_roles.c.role_id)
        .where(Role.name == AGENT_ROLE_NAME, User.is_active.is_(True))
    )
    agents = (await session.execute(stmt)).scalars().all()

    if not agents:
        logger.warning("lead_notification_no_active_agents", role=AGENT_ROLE_NAME)
        return

    notification_service = NotificationService(session)
    title = "New website lead"
    body = f"{customer_name} ({customer_phone}) — {lead_title}"

    for agent in agents:
        notification = await notification_service.create(
            user_id=agent.id,
            title=title,
            body=body,
            notification_type=NotificationType.LEAD,
            entity_type="lead",
            entity_id=lead_id,
        )
        await manager.send_to_user(
            agent.id,
            build_event(
                WSEventType.NOTIFICATION,
                {
                    "id": str(notification.id),
                    "title": title,
                    "body": body,
                    "notification_type": "lead",
                    "entity_type": "lead",
                    "entity_id": str(lead_id),
                },
            ),
        )

    logger.info(
        "lead_agents_notified",
        lead_id=str(lead_id),
        agent_count=len(agents),
    )
