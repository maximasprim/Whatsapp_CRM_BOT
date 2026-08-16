"""
Updated CRM repositories — all tenant-aware.
Replace the contents of app/repositories/crm.py with this file.
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import or_, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.activity import Activity
from app.models.appointment import Appointment
from app.models.campaign import Campaign, CampaignRecipient
from app.models.company import Company
from app.models.conversation import Conversation, ConversationMessage
from app.models.customer import Customer
from app.models.follow_up import FollowUp
from app.models.knowledge_document import DocumentChunk, KnowledgeDocument
from app.models.lead import Lead, LeadStage
from app.models.note import Note
from app.models.notification import Notification
from app.models.order import Order, OrderItem, Payment
from app.models.product import Product
from app.models.tag import Tag
from app.models.task import Task
from app.models.ticket import SupportTicket, TicketMessage
from app.models.whatsapp_template import WhatsAppTemplate
from app.repositories.base_tenant_repository import BaseTenantRepository


# ── Customer ──────────────────────────────────────────────────────────────────

class CustomerRepository(BaseTenantRepository[Customer]):
    model = Customer

    async def get_all(
        self,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
        status: str | None = None,
        assigned_to: uuid.UUID | None = None,
        order_by=None,
    ) -> tuple[list[Customer], int]:
        stmt = self._base_query()

        if search:
            stmt = stmt.where(
                or_(
                    Customer.first_name.ilike(f"%{search}%"),
                    Customer.last_name.ilike(f"%{search}%"),
                    Customer.email.ilike(f"%{search}%"),
                    Customer.phone.ilike(f"%{search}%"),
                )
            )
        if status:
            stmt = stmt.where(Customer.status == status)
        if assigned_to:
            stmt = stmt.where(Customer.assigned_to == assigned_to)

        stmt = stmt.order_by(Customer.created_at.desc())
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def get_by_phone(self, phone: str) -> Customer | None:
        result = await self.session.execute(
            self._base_query().where(Customer.phone == phone)
        )
        return result.scalars().first()

    async def get_by_whatsapp_id(self, whatsapp_id: str) -> Customer | None:
        result = await self.session.execute(
            self._base_query().where(Customer.whatsapp_id == whatsapp_id)
        )
        return result.scalars().first()

    async def get_by_email(self, email: str) -> Customer | None:
        result = await self.session.execute(
            self._base_query().where(Customer.email == email.lower())
        )
        return result.scalars().first()

    async def get_inactive(self, days: int = 30) -> list[Customer]:
        from datetime import datetime, timedelta, timezone
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        result = await self.session.execute(
            self._base_query()
            .where(Customer.last_contact_at < cutoff)
            .where(Customer.status == "active")
        )
        return list(result.scalars().all())

    # Alias kept for callers using the pre-refactor name.
    async def get_inactive_customers(self, days: int = 30) -> list[Customer]:
        return await self.get_inactive(days=days)

    async def search(self, query: str, offset: int = 0, limit: int = 20) -> list[Customer]:
        pattern = f"%{query}%"
        stmt = (
            self._base_query()
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
        return list(result.scalars().all())

    async def search_count(self, query: str) -> int:
        pattern = f"%{query}%"
        stmt = select(func.count()).select_from(
            self._base_query()
            .where(
                or_(
                    Customer.first_name.ilike(pattern),
                    Customer.last_name.ilike(pattern),
                    Customer.email.ilike(pattern),
                    Customer.phone.ilike(pattern),
                )
            )
            .subquery()
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def filter_customers(
        self,
        *,
        status: str | None = None,
        assigned_to: uuid.UUID | None = None,
        company_id: uuid.UUID | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Customer], int]:
        stmt = self._base_query()
        if status:
            stmt = stmt.where(Customer.status == status)
        if assigned_to:
            stmt = stmt.where(Customer.assigned_to == assigned_to)
        if company_id:
            stmt = stmt.where(Customer.company_id == company_id)
        stmt = stmt.order_by(Customer.created_at.desc())
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()
        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total


# ── Company ───────────────────────────────────────────────────────────────────

class CompanyRepository(BaseTenantRepository[Company]):
    model = Company

    async def get_all(
        self,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
    ) -> tuple[list[Company], int]:
        stmt = self._base_query()
        if search:
            stmt = stmt.where(
                or_(
                    Company.name.ilike(f"%{search}%"),
                    Company.domain.ilike(f"%{search}%"),
                    Company.industry.ilike(f"%{search}%"),
                )
            )
        stmt = stmt.order_by(Company.name.asc())
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def search(self, query: str, offset: int = 0, limit: int = 20) -> list[Company]:
        pattern = f"%{query}%"
        stmt = (
            self._base_query()
            .where(or_(Company.name.ilike(pattern), Company.domain.ilike(pattern)))
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


# ── Lead ──────────────────────────────────────────────────────────────────────

class LeadRepository(BaseTenantRepository[Lead]):
    model = Lead

    async def get_all(
        self,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
        status: str | None = None,
        assigned_to: uuid.UUID | None = None,
        customer_id: uuid.UUID | None = None,
    ) -> tuple[list[Lead], int]:
        stmt = self._base_query()
        if search:
            stmt = stmt.where(Lead.title.ilike(f"%{search}%"))
        if status:
            stmt = stmt.where(Lead.status == status)
        if assigned_to:
            stmt = stmt.where(Lead.assigned_to == assigned_to)
        if customer_id:
            stmt = stmt.where(Lead.customer_id == customer_id)
        stmt = stmt.order_by(Lead.created_at.desc())
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def get_pipeline(self) -> dict[str, list[Lead]]:
        """Get all leads grouped by status for Kanban view."""
        result = await self.session.execute(
            self._base_query().order_by(Lead.created_at.desc())
        )
        leads = result.scalars().all()
        pipeline: dict[str, list[Lead]] = {}
        for lead in leads:
            pipeline.setdefault(lead.status, []).append(lead)
        return pipeline

    async def filter_leads(
        self,
        *,
        status: str | None = None,
        assigned_to: uuid.UUID | None = None,
        stage_id: uuid.UUID | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Lead], int]:
        stmt = self._base_query()
        if status:
            stmt = stmt.where(Lead.status == status)
        if assigned_to:
            stmt = stmt.where(Lead.assigned_to == assigned_to)
        if stage_id:
            stmt = stmt.where(Lead.stage_id == stage_id)
        stmt = stmt.order_by(Lead.created_at.desc())
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()
        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def get_pipeline_stats(self) -> dict[str, Any]:
        stmt = (
            select(Lead.status, func.count(Lead.id), func.sum(Lead.estimated_value))
            .where(Lead.tenant_id == self.tenant_id)
            .group_by(Lead.status)
        )
        result = await self.session.execute(stmt)
        rows = result.all()
        return {row[0]: {"count": row[1], "value": float(row[2] or 0)} for row in rows}


# ── Product ───────────────────────────────────────────────────────────────────

class ProductRepository(BaseTenantRepository[Product]):
    model = Product

    async def get_all(
        self,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
        category: str | None = None,
        low_stock: bool = False,
    ) -> tuple[list[Product], int]:
        stmt = self._base_query()
        if search:
            stmt = stmt.where(
                or_(
                    Product.name.ilike(f"%{search}%"),
                    Product.sku.ilike(f"%{search}%"),
                    Product.category.ilike(f"%{search}%"),
                )
            )
        if category:
            stmt = stmt.where(Product.category == category)
        if low_stock:
            stmt = stmt.where(Product.stock_quantity <= 10)
        stmt = stmt.order_by(Product.name.asc())
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def get_by_sku(self, sku: str) -> Product | None:
        result = await self.session.execute(
            self._base_query().where(Product.sku == sku)
        )
        return result.scalars().first()

    async def search(self, query: str, offset: int = 0, limit: int = 20) -> list[Product]:
        pattern = f"%{query}%"
        stmt = (
            self._base_query()
            .where(
                or_(
                    Product.name.ilike(pattern),
                    Product.sku.ilike(pattern),
                    Product.category.ilike(pattern),
                )
            )
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


# ── Order ─────────────────────────────────────────────────────────────────────

class OrderRepository(BaseTenantRepository[Order]):
    model = Order

    async def get_all(
        self,
        page: int = 1,
        page_size: int = 20,
        customer_id: uuid.UUID | None = None,
        status: str | None = None,
    ) -> tuple[list[Order], int]:
        stmt = self._base_query()
        if customer_id:
            stmt = stmt.where(Order.customer_id == customer_id)
        if status:
            stmt = stmt.where(Order.status == status)
        stmt = stmt.order_by(Order.created_at.desc())
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def get_by_customer(self, customer_id: uuid.UUID) -> list[Order]:
        stmt = (
            self._base_query()
            .where(Order.customer_id == customer_id)
            .options(selectinload(Order.items))
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_with_items(self, order_id: uuid.UUID) -> Order | None:
        stmt = (
            self._base_query()
            .where(Order.id == order_id)
            .options(selectinload(Order.items), selectinload(Order.payments))
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()


# ── Appointment ───────────────────────────────────────────────────────────────

class AppointmentRepository(BaseTenantRepository[Appointment]):
    model = Appointment

    async def get_all(
        self,
        page: int = 1,
        page_size: int = 20,
        assigned_to: uuid.UUID | None = None,
        status: str | None = None,
        upcoming_only: bool = False,
    ) -> tuple[list[Appointment], int]:
        from datetime import datetime, timezone
        stmt = self._base_query()
        if assigned_to:
            stmt = stmt.where(Appointment.assigned_to == assigned_to)
        if status:
            stmt = stmt.where(Appointment.status == status)
        if upcoming_only:
            stmt = stmt.where(Appointment.start_time >= datetime.now(timezone.utc))
        stmt = stmt.order_by(Appointment.start_time.asc())
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def get_upcoming_reminders(self) -> list[Appointment]:
        """Get appointments starting in the next 60 minutes."""
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        soon = now + timedelta(minutes=60)
        result = await self.session.execute(
            self._base_query()
            .where(Appointment.start_time.between(now, soon))
            .where(Appointment.status == "confirmed")
            .where(Appointment.reminder_sent == False)
        )
        return list(result.scalars().all())

    # Alias kept for callers using the pre-refactor name.
    async def get_upcoming(self, minutes_ahead: int = 30) -> list[Appointment]:
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(minutes=minutes_ahead)
        result = await self.session.execute(
            self._base_query()
            .where(Appointment.start_time >= now)
            .where(Appointment.start_time <= cutoff)
            .where(Appointment.status == "confirmed")
            .where(Appointment.reminder_sent == False)
        )
        return list(result.scalars().all())

    async def get_by_customer(self, customer_id: uuid.UUID) -> list[Appointment]:
        result = await self.session.execute(
            self._base_query().where(Appointment.customer_id == customer_id)
        )
        return list(result.scalars().all())

    async def filter_appointments(
        self,
        *,
        assigned_to: uuid.UUID | None = None,
        start_date=None,
        end_date=None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Appointment], int]:
        stmt = self._base_query()
        if assigned_to:
            stmt = stmt.where(Appointment.assigned_to == assigned_to)
        if start_date:
            stmt = stmt.where(Appointment.start_time >= start_date)
        if end_date:
            stmt = stmt.where(Appointment.end_time <= end_date)
        stmt = stmt.order_by(Appointment.start_time.asc())
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()
        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total


# ── Task ──────────────────────────────────────────────────────────────────────

class TaskRepository(BaseTenantRepository[Task]):
    model = Task

    async def get_all(
        self,
        page: int = 1,
        page_size: int = 200,
        assigned_to: uuid.UUID | None = None,
        status: str | None = None,
        customer_id: uuid.UUID | None = None,
    ) -> tuple[list[Task], int]:
        stmt = self._base_query()
        if assigned_to:
            stmt = stmt.where(Task.assigned_to == assigned_to)
        if status:
            stmt = stmt.where(Task.status == status)
        if customer_id:
            stmt = stmt.where(Task.customer_id == customer_id)
        stmt = stmt.order_by(Task.due_date.asc().nullslast())
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def get_overdue(self) -> list[Task]:
        from datetime import datetime, timezone
        result = await self.session.execute(
            self._base_query()
            .where(Task.due_date < datetime.now(timezone.utc))
            .where(Task.status.notin_(["done", "cancelled"]))
        )
        return list(result.scalars().all())


# ── Campaign ──────────────────────────────────────────────────────────────────

class CampaignRepository(BaseTenantRepository[Campaign]):
    model = Campaign

    async def get_all(
        self,
        page: int = 1,
        page_size: int = 20,
        offset: int | None = None,
        limit: int | None = None,
        order_by=None,
    ) -> tuple[list[Campaign], int]:
        """Accepts either page/page_size or offset/limit for backward compatibility."""
        stmt = self._base_query()
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        else:
            stmt = stmt.order_by(Campaign.created_at.desc())
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()
        if offset is not None or limit is not None:
            stmt = stmt.offset(offset or 0).limit(limit or 20)
        else:
            stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def get_scheduled(self) -> list[Campaign]:
        from datetime import datetime, timezone
        result = await self.session.execute(
            self._base_query()
            .where(Campaign.status == "scheduled")
            .where(Campaign.scheduled_at <= datetime.now(timezone.utc))
        )
        return list(result.scalars().all())

    # Alias kept for callers using the pre-refactor name.
    async def get_scheduled_campaigns(self) -> list[Campaign]:
        return await self.get_scheduled()

    async def get_pending_recipients(self, campaign_id: uuid.UUID, limit: int = 100) -> list[CampaignRecipient]:
        from app.models.campaign import RecipientStatus
        stmt = (
            select(CampaignRecipient)
            .where(
                CampaignRecipient.campaign_id == campaign_id,
                CampaignRecipient.tenant_id == self.tenant_id,
                CampaignRecipient.status == RecipientStatus.PENDING,
            )
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


# ── Ticket ────────────────────────────────────────────────────────────────────

class TicketRepository(BaseTenantRepository[SupportTicket]):
    model = SupportTicket

    async def get_all(
        self,
        page: int = 1,
        page_size: int = 20,
        offset: int | None = None,
        limit: int | None = None,
        status: str | None = None,
        priority: str | None = None,
        assigned_to: uuid.UUID | None = None,
        customer_id: uuid.UUID | None = None,
    ) -> tuple[list[SupportTicket], int]:
        """Accepts either page/page_size or offset/limit for backward compatibility."""
        stmt = self._base_query()
        if status:
            stmt = stmt.where(SupportTicket.status == status)
        if priority:
            stmt = stmt.where(SupportTicket.priority == priority)
        if assigned_to:
            stmt = stmt.where(SupportTicket.assigned_to == assigned_to)
        if customer_id:
            stmt = stmt.where(SupportTicket.customer_id == customer_id)
        stmt = stmt.order_by(SupportTicket.created_at.desc())
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()
        if offset is not None or limit is not None:
            stmt = stmt.offset(offset or 0).limit(limit or 20)
        else:
            stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def get_by_customer(self, customer_id: uuid.UUID) -> list[SupportTicket]:
        result = await self.session.execute(
            self._base_query().where(SupportTicket.customer_id == customer_id)
        )
        return list(result.scalars().all())


# ── Conversation ──────────────────────────────────────────────────────────────

class ConversationRepository(BaseTenantRepository[Conversation]):
    model = Conversation

    async def get_all(
        self,
        page: int = 1,
        page_size: int = 50,
        status: str | None = None,
        assigned_to: uuid.UUID | None = None,
        is_bot_active: bool | None = None,
    ) -> tuple[list[Conversation], int]:
        stmt = self._base_query()
        if status:
            stmt = stmt.where(Conversation.status == status)
        if assigned_to:
            stmt = stmt.where(Conversation.assigned_to == assigned_to)
        if is_bot_active is not None:
            stmt = stmt.where(Conversation.is_bot_active == is_bot_active)
        stmt = stmt.order_by(Conversation.last_message_at.desc().nullslast())
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def get_by_phone(self, phone_number: str) -> Conversation | None:
        result = await self.session.execute(
            self._base_query().where(Conversation.phone_number == phone_number)
        )
        return result.scalars().first()

    async def get_open_bot_conversations(self) -> list[Conversation]:
        result = await self.session.execute(
            self._base_query()
            .where(Conversation.is_bot_active == True)
            .where(Conversation.status.notin_(["resolved", "closed"]))
        )
        return list(result.scalars().all())


# ── Notification ──────────────────────────────────────────────────────────────

class NotificationRepository(BaseTenantRepository[Notification]):
    model = Notification

    async def get_for_user(
        self,
        user_id: uuid.UUID,
        page: int = 1,
        page_size: int = 30,
        unread_only: bool = False,
    ) -> tuple[list[Notification], int]:
        stmt = self._base_query().where(Notification.user_id == user_id)
        if unread_only:
            stmt = stmt.where(Notification.is_read == False)
        stmt = stmt.order_by(Notification.created_at.desc())
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    # Alias kept for callers using the pre-refactor name/signature.
    async def get_user_notifications(
        self, user_id: uuid.UUID, unread_only: bool = False, offset: int = 0, limit: int = 20
    ) -> tuple[list[Notification], int]:
        page = (offset // limit) + 1 if limit else 1
        return await self.get_for_user(user_id, page=page, page_size=limit or 20, unread_only=unread_only)

    async def mark_all_read(self, user_id: uuid.UUID) -> int:
        from sqlalchemy import update
        result = await self.session.execute(
            update(Notification)
            .where(Notification.tenant_id == self.tenant_id)
            .where(Notification.user_id == user_id)
            .where(Notification.is_read == False)
            .values(is_read=True)
        )
        await self.session.flush()
        return result.rowcount


# ── Activity ──────────────────────────────────────────────────────────────────

class ActivityRepository(BaseTenantRepository[Activity]):
    model = Activity

    async def log(
        self,
        customer_id: uuid.UUID,
        activity_type: Any,
        title: str,
        description: str = "",
        metadata: dict | None = None,
        user_id: uuid.UUID | None = None,
        entity_type: str | None = None,
        entity_id: uuid.UUID | None = None,
    ) -> Activity:
        return await self.create(
            customer_id=customer_id,
            user_id=user_id,
            activity_type=activity_type,
            title=title,
            description=description,
            metadata=metadata or {},
            entity_type=entity_type,
            entity_id=entity_id,
        )

    async def get_for_customer(
        self,
        customer_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Activity], int]:
        stmt = self._base_query().where(Activity.customer_id == customer_id)
        stmt = stmt.order_by(Activity.created_at.desc())
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total


# ── Note ──────────────────────────────────────────────────────────────────────

class NoteRepository(BaseTenantRepository[Note]):
    model = Note

    async def get_for_customer(
        self, customer_id: uuid.UUID
    ) -> list[Note]:
        result = await self.session.execute(
            self._base_query()
            .where(Note.customer_id == customer_id)
            .order_by(Note.is_pinned.desc(), Note.created_at.desc())
        )
        return list(result.scalars().all())

    # Alias kept for callers using the pre-refactor name.
    async def get_by_customer(self, customer_id: uuid.UUID) -> list[Note]:
        return await self.get_for_customer(customer_id)

# ── FollowUp ──────────────────────────────────────────────────────────────────

class FollowUpRepository(BaseTenantRepository[FollowUp]):
    model = FollowUp

    async def get_due(self) -> list[FollowUp]:
        from datetime import datetime, timezone
        result = await self.session.execute(
            self._base_query()
            .where(FollowUp.scheduled_at <= datetime.now(timezone.utc))
            .where(FollowUp.status == "pending")
        )
        return list(result.scalars().all())

    # Alias kept for callers using the pre-refactor name.
    async def get_due_followups(self) -> list[FollowUp]:
        return await self.get_due()

    async def get_for_customer(
        self, customer_id: uuid.UUID
    ) -> list[FollowUp]:
        result = await self.session.execute(
            self._base_query()
            .where(FollowUp.customer_id == customer_id)
            .order_by(FollowUp.scheduled_at.asc())
        )
        return list(result.scalars().all())


# ── Knowledge Document ────────────────────────────────────────────────────────

class KnowledgeDocumentRepository(BaseTenantRepository[KnowledgeDocument]):
    model = KnowledgeDocument

    async def get_ready(self) -> list[KnowledgeDocument]:
        result = await self.session.execute(
            self._base_query().where(KnowledgeDocument.status == "ready")
        )
        return list(result.scalars().all())


# ── WhatsApp Template ─────────────────────────────────────────────────────────

class WhatsAppTemplateRepository(BaseTenantRepository[WhatsAppTemplate]):
    model = WhatsAppTemplate

    async def get_by_name(self, name: str) -> WhatsAppTemplate | None:
        result = await self.session.execute(
            self._base_query().where(WhatsAppTemplate.name == name)
        )
        return result.scalars().first()

    async def get_approved(self) -> list[WhatsAppTemplate]:
        result = await self.session.execute(
            self._base_query().where(WhatsAppTemplate.status == "approved")
        )
        return list(result.scalars().all())
