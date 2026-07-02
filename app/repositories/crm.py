from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Sequence

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.activity import Activity, ActivityType
from app.models.appointment import Appointment, AppointmentStatus
from app.models.campaign import Campaign, CampaignRecipient, CampaignStatus
from app.models.company import Company
from app.models.customer import Customer, CustomerStatus
from app.models.followup import FollowUp, FollowUpStatus
from app.models.lead import Lead, LeadStage, LeadStatus
from app.models.note import Note
from app.models.notification import Notification
from app.models.order import Order, OrderItem, Payment
from app.models.product import Product
from app.models.task import Task, TaskStatus
from app.models.ticket import SupportTicket, TicketMessage
from app.repositories.base import BaseRepository


class CustomerRepository(BaseRepository[Customer]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Customer, session)

    async def get_by_phone(self, phone: str) -> Customer | None:
        return await self.get_by_field("phone", phone)

    async def get_by_whatsapp_id(self, whatsapp_id: str) -> Customer | None:
        return await self.get_by_field("whatsapp_id", whatsapp_id)

    async def search(self, query: str, offset: int = 0, limit: int = 20) -> Sequence[Customer]:
        pattern = f"%{query}%"
        stmt = (
            select(Customer)
            .where(
                or_(
                    Customer.first_name.ilike(pattern),
                    Customer.last_name.ilike(pattern),
                    Customer.email.ilike(pattern),
                    Customer.phone.ilike(pattern),
                )
            )
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def search_count(self, query: str) -> int:
        pattern = f"%{query}%"
        stmt = select(func.count()).select_from(Customer).where(
            or_(
                Customer.first_name.ilike(pattern),
                Customer.last_name.ilike(pattern),
                Customer.email.ilike(pattern),
                Customer.phone.ilike(pattern),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def filter_customers(
        self,
        *,
        status: str | None = None,
        assigned_to: uuid.UUID | None = None,
        company_id: uuid.UUID | None = None,
        industry: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[Sequence[Customer], int]:
        conditions = []
        if status:
            conditions.append(Customer.status == status)
        if assigned_to:
            conditions.append(Customer.assigned_to == assigned_to)
        if company_id:
            conditions.append(Customer.company_id == company_id)
        if industry:
            conditions.append(Customer.industry.ilike(f"%{industry}%"))

        base = select(Customer).where(and_(*conditions)) if conditions else select(Customer)
        count_stmt = select(func.count()).select_from(Customer).where(and_(*conditions)) if conditions else select(func.count()).select_from(Customer)

        count = (await self.session.execute(count_stmt)).scalar_one()
        items = (await self.session.execute(base.offset(offset).limit(limit))).scalars().all()
        return items, count

    async def get_inactive_customers(self, days: int = 30) -> Sequence[Customer]:
        from datetime import timedelta
        cutoff = datetime.now(UTC) - timedelta(days=days)
        stmt = select(Customer).where(
            and_(
                Customer.status == CustomerStatus.ACTIVE,
                Customer.updated_at < cutoff,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()


class CompanyRepository(BaseRepository[Company]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Company, session)

    async def get_by_domain(self, domain: str) -> Company | None:
        return await self.get_by_field("domain", domain)

    async def search(self, query: str, offset: int = 0, limit: int = 20) -> Sequence[Company]:
        pattern = f"%{query}%"
        stmt = select(Company).where(
            or_(Company.name.ilike(pattern), Company.domain.ilike(pattern))
        ).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()


class LeadRepository(BaseRepository[Lead]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Lead, session)

    async def get_by_customer(self, customer_id: uuid.UUID) -> Sequence[Lead]:
        stmt = select(Lead).where(Lead.customer_id == customer_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def filter_leads(
        self,
        *,
        status: str | None = None,
        assigned_to: uuid.UUID | None = None,
        stage_id: uuid.UUID | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[Sequence[Lead], int]:
        conditions = []
        if status:
            conditions.append(Lead.status == status)
        if assigned_to:
            conditions.append(Lead.assigned_to == assigned_to)
        if stage_id:
            conditions.append(Lead.stage_id == stage_id)
        where_clause = and_(*conditions) if conditions else True
        count = (await self.session.execute(select(func.count()).select_from(Lead).where(where_clause))).scalar_one()
        items = (await self.session.execute(select(Lead).where(where_clause).offset(offset).limit(limit))).scalars().all()
        return items, count

    async def get_pipeline_stats(self) -> dict[str, Any]:
        stmt = select(Lead.status, func.count(Lead.id), func.sum(Lead.estimated_value)).group_by(Lead.status)
        result = await self.session.execute(stmt)
        rows = result.all()
        return {row[0]: {"count": row[1], "value": float(row[2] or 0)} for row in rows}


class ProductRepository(BaseRepository[Product]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Product, session)

    async def get_by_sku(self, sku: str) -> Product | None:
        return await self.get_by_field("sku", sku)

    async def search(self, query: str, offset: int = 0, limit: int = 20) -> Sequence[Product]:
        pattern = f"%{query}%"
        stmt = select(Product).where(
            or_(Product.name.ilike(pattern), Product.sku.ilike(pattern), Product.category.ilike(pattern))
        ).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()


class OrderRepository(BaseRepository[Order]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Order, session)

    async def get_by_order_number(self, order_number: str) -> Order | None:
        return await self.get_by_field("order_number", order_number)

    async def get_by_customer(self, customer_id: uuid.UUID) -> Sequence[Order]:
        stmt = (
            select(Order)
            .where(Order.customer_id == customer_id)
            .options(selectinload(Order.items))
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_with_items(self, order_id: uuid.UUID) -> Order | None:
        stmt = select(Order).where(Order.id == order_id).options(selectinload(Order.items), selectinload(Order.payments))
        result = await self.session.execute(stmt)
        return result.scalars().first()


class AppointmentRepository(BaseRepository[Appointment]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Appointment, session)

    async def get_upcoming(self, minutes_ahead: int = 30) -> Sequence[Appointment]:
        from datetime import timedelta
        now = datetime.now(UTC)
        cutoff = now + timedelta(minutes=minutes_ahead)
        stmt = select(Appointment).where(
            and_(
                Appointment.start_time >= now,
                Appointment.start_time <= cutoff,
                Appointment.status == AppointmentStatus.CONFIRMED,
                Appointment.reminder_sent == False,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_customer(self, customer_id: uuid.UUID) -> Sequence[Appointment]:
        stmt = select(Appointment).where(Appointment.customer_id == customer_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()


class TaskRepository(BaseRepository[Task]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Task, session)

    async def get_overdue(self) -> Sequence[Task]:
        now = datetime.now(UTC)
        stmt = select(Task).where(
            and_(
                Task.due_date < now,
                Task.status.notin_([TaskStatus.DONE, TaskStatus.CANCELLED]),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_customer(self, customer_id: uuid.UUID) -> Sequence[Task]:
        stmt = select(Task).where(Task.customer_id == customer_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()


class FollowUpRepository(BaseRepository[FollowUp]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(FollowUp, session)

    async def get_due_followups(self) -> Sequence[FollowUp]:
        now = datetime.now(UTC)
        stmt = select(FollowUp).where(
            and_(
                FollowUp.scheduled_at <= now,
                FollowUp.status == FollowUpStatus.PENDING,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()


class CampaignRepository(BaseRepository[Campaign]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Campaign, session)

    async def get_scheduled_campaigns(self) -> Sequence[Campaign]:
        now = datetime.now(UTC)
        stmt = select(Campaign).where(
            and_(
                Campaign.status == CampaignStatus.SCHEDULED,
                Campaign.scheduled_at <= now,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_pending_recipients(self, campaign_id: uuid.UUID, limit: int = 100) -> Sequence[CampaignRecipient]:
        from app.models.campaign import RecipientStatus
        stmt = select(CampaignRecipient).where(
            and_(
                CampaignRecipient.campaign_id == campaign_id,
                CampaignRecipient.status == RecipientStatus.PENDING,
            )
        ).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()


class TicketRepository(BaseRepository[SupportTicket]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(SupportTicket, session)

    async def get_by_ticket_number(self, ticket_number: str) -> SupportTicket | None:
        return await self.get_by_field("ticket_number", ticket_number)

    async def get_by_customer(self, customer_id: uuid.UUID) -> Sequence[SupportTicket]:
        stmt = select(SupportTicket).where(SupportTicket.customer_id == customer_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()


class NoteRepository(BaseRepository[Note]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Note, session)

    async def get_by_customer(self, customer_id: uuid.UUID) -> Sequence[Note]:
        stmt = select(Note).where(Note.customer_id == customer_id).order_by(Note.is_pinned.desc(), Note.created_at.desc())
        result = await self.session.execute(stmt)
        return result.scalars().all()


class ActivityRepository(BaseRepository[Activity]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Activity, session)

    async def get_by_customer(self, customer_id: uuid.UUID, limit: int = 50) -> Sequence[Activity]:
        stmt = select(Activity).where(Activity.customer_id == customer_id).order_by(Activity.created_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def log(
        self,
        customer_id: uuid.UUID,
        activity_type: ActivityType,
        title: str,
        description: str | None = None,
        user_id: uuid.UUID | None = None,
        entity_type: str | None = None,
        entity_id: uuid.UUID | None = None,
        metadata: dict | None = None,
    ) -> Activity:
        return await self.create(
            customer_id=customer_id,
            user_id=user_id,
            activity_type=activity_type,
            title=title,
            description=description,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata_=metadata,
        )


class NotificationRepository(BaseRepository[Notification]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Notification, session)

    async def get_user_notifications(
        self, user_id: uuid.UUID, unread_only: bool = False, offset: int = 0, limit: int = 20
    ) -> tuple[Sequence[Notification], int]:
        conditions = [Notification.user_id == user_id]
        if unread_only:
            conditions.append(Notification.is_read == False)
        where = and_(*conditions)
        count = (await self.session.execute(select(func.count()).select_from(Notification).where(where))).scalar_one()
        items = (await self.session.execute(select(Notification).where(where).order_by(Notification.created_at.desc()).offset(offset).limit(limit))).scalars().all()
        return items, count

    async def mark_all_read(self, user_id: uuid.UUID) -> None:
        from sqlalchemy import update
        now = datetime.now(UTC)
        stmt = select(Notification).where(and_(Notification.user_id == user_id, Notification.is_read == False))
        result = await self.session.execute(stmt)
        notifs = result.scalars().all()
        for n in notifs:
            n.is_read = True
            n.read_at = now
        await self.session.flush()
