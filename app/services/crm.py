from __future__ import annotations

import random
import string
import uuid
from datetime import UTC, datetime
from typing import Any, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException, NotFoundException
from app.models.activity import ActivityType
from app.models.appointment import Appointment
from app.models.campaign import Campaign, CampaignRecipient, CampaignStatus
from app.models.company import Company
from app.models.customer import Customer
from app.models.followup import FollowUp
from app.models.lead import Lead, LeadStage
from app.models.note import Note
from app.models.notification import Notification, NotificationType
from app.models.order import Order, OrderItem, Payment
from app.models.product import Product
from app.models.task import Task
from app.models.ticket import SupportTicket, TicketMessage
from app.repositories.crm import (
    ActivityRepository, AppointmentRepository, CampaignRepository,
    CompanyRepository, CustomerRepository, FollowUpRepository,
    LeadRepository, NoteRepository, NotificationRepository,
    OrderRepository, ProductRepository, TaskRepository, TicketRepository,
)
from app.schemas.crm import (
    AppointmentCreate, AppointmentUpdate, CampaignCreate, CampaignUpdate,
    CompanyCreate, CompanyUpdate, CustomerCreate, CustomerUpdate,
    FollowUpCreate, LeadCreate, LeadUpdate, NoteCreate,
    OrderCreate, ProductCreate, ProductUpdate, TaskCreate, TaskUpdate,
    TicketCreate, TicketUpdate,
)


def _generate_order_number() -> str:
    return "ORD-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))


def _generate_ticket_number() -> str:
    return "TKT-" + "".join(random.choices(string.digits, k=6))


class CustomerService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = CustomerRepository(session)
        self.activity_repo = ActivityRepository(session)
        self.session = session

    async def create(self, data: CustomerCreate, created_by: uuid.UUID | None = None) -> Customer:
        existing = await self.repo.get_by_phone(data.phone)
        if existing:
            raise ConflictException(f"Customer with phone {data.phone} already exists.")
        customer = await self.repo.create(**data.model_dump())
        await self.activity_repo.log(
            customer_id=customer.id,
            activity_type=ActivityType.STATUS_CHANGE,
            title="Customer created",
            user_id=created_by,
        )
        return customer

    async def get_or_create_by_whatsapp(self, whatsapp_id: str, phone: str, name: str = "") -> tuple[Customer, bool]:
        customer = await self.repo.get_by_whatsapp_id(whatsapp_id)
        if customer:
            return customer, False
        first, *rest = (name or "Unknown").split(" ", 1)
        customer = await self.repo.create(
            first_name=first,
            last_name=rest[0] if rest else "",
            phone=phone,
            whatsapp_id=whatsapp_id,
            source="whatsapp",
        )
        return customer, True

    async def list(
        self,
        *,
        search: str | None = None,
        status: str | None = None,
        assigned_to: uuid.UUID | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[Sequence[Customer], int]:
        if search:
            items = await self.repo.search(search, offset=offset, limit=limit)
            count = await self.repo.search_count(search)
            return items, count
        return await self.repo.filter_customers(
            status=status, assigned_to=assigned_to, offset=offset, limit=limit
        )

    async def get(self, customer_id: uuid.UUID) -> Customer:
        return await self.repo.get_by_id_or_raise(customer_id)

    async def update(self, customer_id: uuid.UUID, data: CustomerUpdate, updated_by: uuid.UUID | None = None) -> Customer:
        customer = await self.repo.get_by_id_or_raise(customer_id)
        updated = await self.repo.update(customer, **data.model_dump(exclude_unset=True))
        await self.activity_repo.log(
            customer_id=customer_id,
            activity_type=ActivityType.STATUS_CHANGE,
            title="Customer updated",
            user_id=updated_by,
        )
        return updated

    async def delete(self, customer_id: uuid.UUID) -> None:
        await self.repo.delete_by_id(customer_id)


class CompanyService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = CompanyRepository(session)

    async def create(self, data: CompanyCreate) -> Company:
        if data.domain and await self.repo.get_by_domain(data.domain):
            raise ConflictException(f"Company with domain {data.domain} already exists.")
        return await self.repo.create(**data.model_dump())

    async def list(self, search: str | None = None, offset: int = 0, limit: int = 20) -> tuple[Sequence[Company], int]:
        if search:
            items = await self.repo.search(search, offset=offset, limit=limit)
            count = await self.repo.count()
            return items, count
        items = await self.repo.get_all(offset=offset, limit=limit)
        count = await self.repo.count()
        return items, count

    async def get(self, company_id: uuid.UUID) -> Company:
        return await self.repo.get_by_id_or_raise(company_id)

    async def update(self, company_id: uuid.UUID, data: CompanyUpdate) -> Company:
        company = await self.repo.get_by_id_or_raise(company_id)
        return await self.repo.update(company, **data.model_dump(exclude_unset=True))

    async def delete(self, company_id: uuid.UUID) -> None:
        await self.repo.delete_by_id(company_id)


class LeadService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = LeadRepository(session)
        self.activity_repo = ActivityRepository(session)
        self.session = session

    async def create(self, data: LeadCreate, created_by: uuid.UUID | None = None) -> Lead:
        lead = await self.repo.create(**data.model_dump())
        await self.activity_repo.log(
            customer_id=data.customer_id,
            activity_type=ActivityType.LEAD_CREATED,
            title=f"Lead created: {data.title}",
            user_id=created_by,
            entity_type="lead",
            entity_id=lead.id,
        )
        return lead

    async def list(
        self,
        *,
        status: str | None = None,
        assigned_to: uuid.UUID | None = None,
        stage_id: uuid.UUID | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[Sequence[Lead], int]:
        return await self.repo.filter_leads(
            status=status, assigned_to=assigned_to, stage_id=stage_id, offset=offset, limit=limit
        )

    async def get(self, lead_id: uuid.UUID) -> Lead:
        return await self.repo.get_by_id_or_raise(lead_id)

    async def update(self, lead_id: uuid.UUID, data: LeadUpdate, updated_by: uuid.UUID | None = None) -> Lead:
        lead = await self.repo.get_by_id_or_raise(lead_id)
        updated = await self.repo.update(lead, **data.model_dump(exclude_unset=True))
        await self.activity_repo.log(
            customer_id=lead.customer_id,
            activity_type=ActivityType.LEAD_UPDATED,
            title=f"Lead updated: {lead.title}",
            user_id=updated_by,
            entity_type="lead",
            entity_id=lead_id,
        )
        return updated

    async def delete(self, lead_id: uuid.UUID) -> None:
        await self.repo.delete_by_id(lead_id)

    async def get_pipeline_stats(self) -> dict[str, Any]:
        return await self.repo.get_pipeline_stats()


class ProductService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = ProductRepository(session)

    async def create(self, data: ProductCreate) -> Product:
        if data.sku and await self.repo.get_by_sku(data.sku):
            raise ConflictException(f"Product with SKU {data.sku} already exists.")
        return await self.repo.create(**data.model_dump())

    async def list(self, search: str | None = None, offset: int = 0, limit: int = 20) -> tuple[Sequence[Product], int]:
        if search:
            items = await self.repo.search(search, offset=offset, limit=limit)
            return items, len(items)
        items = await self.repo.get_all(offset=offset, limit=limit)
        count = await self.repo.count()
        return items, count

    async def get(self, product_id: uuid.UUID) -> Product:
        return await self.repo.get_by_id_or_raise(product_id)

    async def update(self, product_id: uuid.UUID, data: ProductUpdate) -> Product:
        product = await self.repo.get_by_id_or_raise(product_id)
        return await self.repo.update(product, **data.model_dump(exclude_unset=True))

    async def delete(self, product_id: uuid.UUID) -> None:
        await self.repo.delete_by_id(product_id)


class OrderService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = OrderRepository(session)
        self.product_repo = ProductRepository(session)
        self.activity_repo = ActivityRepository(session)
        self.session = session

    async def create(self, data: OrderCreate, created_by: uuid.UUID | None = None) -> Order:
        subtotal = 0.0
        tax_total = 0.0
        items_data = []
        for item_data in data.items:
            product = await self.product_repo.get_by_id_or_raise(item_data.product_id)
            unit_price = item_data.unit_price if item_data.unit_price is not None else product.price
            line_total = unit_price * item_data.quantity * (1 - item_data.discount / 100)
            tax = line_total * (product.tax_rate / 100)
            subtotal += line_total
            tax_total += tax
            items_data.append({
                "product_id": product.id,
                "product_name": product.name,
                "quantity": item_data.quantity,
                "unit_price": unit_price,
                "discount": item_data.discount,
                "total_price": line_total,
            })
        total = subtotal + tax_total + data.shipping_amount - data.discount_amount
        order = await self.repo.create(
            order_number=_generate_order_number(),
            customer_id=data.customer_id,
            subtotal=round(subtotal, 2),
            tax_amount=round(tax_total, 2),
            discount_amount=round(data.discount_amount, 2),
            shipping_amount=round(data.shipping_amount, 2),
            total_amount=round(total, 2),
            currency=data.currency,
            shipping_address=data.shipping_address,
            billing_address=data.billing_address,
            notes=data.notes,
        )
        for item_kwargs in items_data:
            item = OrderItem(order_id=order.id, **item_kwargs)
            self.session.add(item)
        await self.session.flush()
        await self.activity_repo.log(
            customer_id=data.customer_id,
            activity_type=ActivityType.ORDER_PLACED,
            title=f"Order placed: {order.order_number}",
            user_id=created_by,
            entity_type="order",
            entity_id=order.id,
        )
        try:
            from app.repositories.crm import CustomerRepository
            from app.notifications.engine import NotificationChannel, NotificationEngine
            cust_repo = CustomerRepository(self.session)
            customer = await cust_repo.get_by_id(data.customer_id)
            if customer and customer.phone:
                engine = NotificationEngine(self.session)
                channels = [NotificationChannel.WHATSAPP]
                if customer.email:
                    channels.append(NotificationChannel.EMAIL)
                await engine.send_templated(
                    template_key="order_confirmation",
                    context={
                        "first_name": customer.first_name,
                        "order_number": order.order_number,
                        "currency": order.currency,
                        "total_amount": f"{order.total_amount:.2f}",
                    },
                    channels=channels,
                    whatsapp_to=customer.phone,
                    email_to=customer.email,
                )
        except Exception:
            pass
        return order

    async def get(self, order_id: uuid.UUID) -> Order:
        order = await self.repo.get_with_items(order_id)
        if not order:
            raise NotFoundException("Order not found.")
        return order

    async def get_by_customer(self, customer_id: uuid.UUID) -> Sequence[Order]:
        return await self.repo.get_by_customer(customer_id)


class AppointmentService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = AppointmentRepository(session)
        self.activity_repo = ActivityRepository(session)
        self.session = session

    async def create(self, data: AppointmentCreate, created_by: uuid.UUID | None = None) -> Appointment:
        appt = await self.repo.create(**data.model_dump())
        await self.activity_repo.log(
            customer_id=data.customer_id,
            activity_type=ActivityType.MEETING,
            title=f"Appointment: {data.title}",
            user_id=created_by,
            entity_type="appointment",
            entity_id=appt.id,
        )
        return appt

    async def update(self, appt_id: uuid.UUID, data: AppointmentUpdate) -> Appointment:
        appt = await self.repo.get_by_id_or_raise(appt_id)
        return await self.repo.update(appt, **data.model_dump(exclude_unset=True))

    async def get(self, appt_id: uuid.UUID) -> Appointment:
        return await self.repo.get_by_id_or_raise(appt_id)

    async def list_by_customer(self, customer_id: uuid.UUID) -> Sequence[Appointment]:
        return await self.repo.get_by_customer(customer_id)

    async def cancel(self, appt_id: uuid.UUID, reason: str | None = None) -> Appointment:
        from app.models.appointment import AppointmentStatus
        appt = await self.repo.get_by_id_or_raise(appt_id)
        return await self.repo.update(appt, status=AppointmentStatus.CANCELLED, cancellation_reason=reason)


class TaskService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = TaskRepository(session)
        self.session = session

    async def create(self, data: TaskCreate, created_by: uuid.UUID | None = None) -> Task:
        return await self.repo.create(**data.model_dump(), created_by=created_by)

    async def update(self, task_id: uuid.UUID, data: TaskUpdate) -> Task:
        task = await self.repo.get_by_id_or_raise(task_id)
        updates = data.model_dump(exclude_unset=True)
        if updates.get("status") == "done" and not task.completed_at:
            updates["completed_at"] = datetime.now(UTC)
        return await self.repo.update(task, **updates)

    async def get(self, task_id: uuid.UUID) -> Task:
        return await self.repo.get_by_id_or_raise(task_id)

    async def list(self, assigned_to: uuid.UUID | None = None, offset: int = 0, limit: int = 20) -> tuple[Sequence[Task], int]:
        from sqlalchemy import and_, func, select
        conditions = []
        if assigned_to:
            conditions.append(Task.assigned_to == assigned_to)
        from sqlalchemy import and_
        where = and_(*conditions) if conditions else True
        count = (await self.session.execute(select(func.count()).select_from(Task).where(where))).scalar_one()
        items = (await self.session.execute(select(Task).where(where).offset(offset).limit(limit))).scalars().all()
        return items, count

    async def delete(self, task_id: uuid.UUID) -> None:
        await self.repo.delete_by_id(task_id)


class CampaignService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = CampaignRepository(session)
        self.customer_repo = CustomerRepository(session)
        self.session = session

    async def create(self, data: CampaignCreate, created_by: uuid.UUID | None = None) -> Campaign:
        campaign = await self.repo.create(**data.model_dump(exclude={"audience_filters"}), created_by=created_by, audience_filters=data.audience_filters)
        return campaign

    async def add_recipients(self, campaign_id: uuid.UUID, customer_ids: list[uuid.UUID]) -> int:
        campaign = await self.repo.get_by_id_or_raise(campaign_id)
        count = 0
        for cid in customer_ids:
            recipient = CampaignRecipient(campaign_id=campaign_id, customer_id=cid)
            self.session.add(recipient)
            count += 1
        campaign.total_recipients = count
        self.session.add(campaign)
        await self.session.flush()
        return count

    async def get(self, campaign_id: uuid.UUID) -> Campaign:
        return await self.repo.get_by_id_or_raise(campaign_id)

    async def update(self, campaign_id: uuid.UUID, data: CampaignUpdate) -> Campaign:
        campaign = await self.repo.get_by_id_or_raise(campaign_id)
        return await self.repo.update(campaign, **data.model_dump(exclude_unset=True))

    async def list(self, offset: int = 0, limit: int = 20) -> tuple[Sequence[Campaign], int]:
        items = await self.repo.get_all(offset=offset, limit=limit)
        count = await self.repo.count()
        return items, count


class TicketService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = TicketRepository(session)
        self.activity_repo = ActivityRepository(session)
        self.session = session

    async def create(self, data: TicketCreate, created_by: uuid.UUID | None = None) -> SupportTicket:
        ticket = await self.repo.create(
            **data.model_dump(),
            ticket_number=_generate_ticket_number(),
        )
        await self.activity_repo.log(
            customer_id=data.customer_id,
            activity_type=ActivityType.TICKET_OPENED,
            title=f"Ticket opened: {data.subject}",
            user_id=created_by,
            entity_type="ticket",
            entity_id=ticket.id,
        )
        try:
            from app.repositories.crm import CustomerRepository
            from app.notifications.engine import NotificationChannel, NotificationEngine
            cust_repo = CustomerRepository(self.session)
            customer = await cust_repo.get_by_id(data.customer_id)
            if customer and customer.phone:
                engine = NotificationEngine(self.session)
                channels = [NotificationChannel.WHATSAPP]
                if customer.email:
                    channels.append(NotificationChannel.EMAIL)
                await engine.send_templated(
                    template_key="ticket_created",
                    context={
                        "first_name": customer.first_name,
                        "ticket_number": ticket.ticket_number,
                        "subject": data.subject,
                    },
                    channels=channels,
                    whatsapp_to=customer.phone,
                    email_to=customer.email,
                )
        except Exception:
            pass
        return ticket

    async def update(self, ticket_id: uuid.UUID, data: TicketUpdate) -> SupportTicket:
        ticket = await self.repo.get_by_id_or_raise(ticket_id)
        updates = data.model_dump(exclude_unset=True)
        from app.models.ticket import TicketStatus
        if updates.get("status") == TicketStatus.RESOLVED and not ticket.resolved_at:
            updates["resolved_at"] = datetime.now(UTC)
        if updates.get("status") == TicketStatus.CLOSED and not ticket.closed_at:
            updates["closed_at"] = datetime.now(UTC)
        return await self.repo.update(ticket, **updates)

    async def get(self, ticket_id: uuid.UUID) -> SupportTicket:
        return await self.repo.get_by_id_or_raise(ticket_id)

    async def list(self, offset: int = 0, limit: int = 20) -> tuple[Sequence[SupportTicket], int]:
        items = await self.repo.get_all(offset=offset, limit=limit)
        count = await self.repo.count()
        return items, count

    async def add_message(
        self, ticket_id: uuid.UUID, content: str, sender_id: uuid.UUID | None = None, is_internal: bool = False
    ) -> TicketMessage:
        ticket = await self.repo.get_by_id_or_raise(ticket_id)
        if not ticket.first_response_at and not is_internal and sender_id:
            await self.repo.update(ticket, first_response_at=datetime.now(UTC))
        message = TicketMessage(
            ticket_id=ticket_id,
            sender_id=sender_id,
            content=content,
            is_internal=is_internal,
        )
        self.session.add(message)
        await self.session.flush()
        return message


class NoteService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = NoteRepository(session)

    async def create(self, data: NoteCreate, created_by: uuid.UUID | None = None) -> Note:
        return await self.repo.create(**data.model_dump(), created_by=created_by)

    async def list_by_customer(self, customer_id: uuid.UUID) -> Sequence[Note]:
        return await self.repo.get_by_customer(customer_id)

    async def delete(self, note_id: uuid.UUID) -> None:
        await self.repo.delete_by_id(note_id)


class NotificationService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = NotificationRepository(session)

    async def create(
        self,
        user_id: uuid.UUID,
        title: str,
        body: str,
        notification_type: NotificationType = NotificationType.INFO,
        entity_type: str | None = None,
        entity_id: uuid.UUID | None = None,
        action_url: str | None = None,
    ) -> Notification:
        return await self.repo.create(
            user_id=user_id,
            title=title,
            body=body,
            notification_type=notification_type,
            entity_type=entity_type,
            entity_id=entity_id,
            action_url=action_url,
        )

    async def list(
        self, user_id: uuid.UUID, unread_only: bool = False, offset: int = 0, limit: int = 20
    ) -> tuple[Sequence[Notification], int]:
        return await self.repo.get_user_notifications(user_id, unread_only=unread_only, offset=offset, limit=limit)

    async def mark_read(self, notification_id: uuid.UUID) -> Notification:
        notif = await self.repo.get_by_id_or_raise(notification_id)
        return await self.repo.update(notif, is_read=True, read_at=datetime.now(UTC))

    async def mark_all_read(self, user_id: uuid.UUID) -> None:
        await self.repo.mark_all_read(user_id)
