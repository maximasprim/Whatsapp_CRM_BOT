from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field

from app.models.customer import CustomerGender, CustomerStatus
from app.models.lead import LeadPriority, LeadSource, LeadStatus
from app.models.appointment import AppointmentStatus, AppointmentType
from app.models.task import TaskPriority, TaskStatus
from app.models.campaign import CampaignStatus, CampaignType
from app.models.ticket import TicketPriority, TicketStatus
from app.models.activity import ActivityType
from app.models.notification import NotificationType
from app.models.order import OrderStatus, PaymentStatus
from app.models.company import CompanySize
from app.models.followup import FollowUpStatus, FollowUpType


# ── Customer ──────────────────────────────────────────────────────────────────
class CustomerCreate(BaseModel):
    first_name: str = Field(..., max_length=100)
    last_name: str = Field(..., max_length=100)
    phone: str = Field(..., max_length=30)
    email: EmailStr | None = None
    whatsapp_id: str | None = None
    gender: CustomerGender = CustomerGender.UNKNOWN
    country: str | None = None
    city: str | None = None
    address: str | None = None
    timezone: str | None = None
    language: str | None = None
    job_title: str | None = None
    industry: str | None = None
    company_id: uuid.UUID | None = None
    assigned_to: uuid.UUID | None = None
    source: str | None = None
    custom_fields: dict | None = None


class CustomerUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    gender: CustomerGender | None = None
    status: CustomerStatus | None = None
    country: str | None = None
    city: str | None = None
    address: str | None = None
    timezone: str | None = None
    language: str | None = None
    job_title: str | None = None
    industry: str | None = None
    company_id: uuid.UUID | None = None
    assigned_to: uuid.UUID | None = None
    source: str | None = None
    custom_fields: dict | None = None


class CustomerResponse(BaseModel):
    id: uuid.UUID
    first_name: str
    last_name: str
    email: str | None
    phone: str
    whatsapp_id: str | None
    gender: CustomerGender
    status: CustomerStatus
    is_verified: bool
    country: str | None
    city: str | None
    job_title: str | None
    industry: str | None
    company_id: uuid.UUID | None
    assigned_to: uuid.UUID | None
    lead_score: int
    lifetime_value: float
    total_orders: int
    sentiment_score: float | None
    intent_summary: str | None
    source: str | None
    custom_fields: dict | None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# ── Company ───────────────────────────────────────────────────────────────────
class CompanyCreate(BaseModel):
    name: str = Field(..., max_length=255)
    domain: str | None = None
    industry: str | None = None
    size: CompanySize | None = None
    employee_count: int | None = None
    phone: str | None = None
    email: EmailStr | None = None
    website: str | None = None
    country: str | None = None
    city: str | None = None
    description: str | None = None


class CompanyUpdate(BaseModel):
    name: str | None = None
    domain: str | None = None
    industry: str | None = None
    size: CompanySize | None = None
    employee_count: int | None = None
    phone: str | None = None
    email: EmailStr | None = None
    website: str | None = None
    country: str | None = None
    city: str | None = None
    description: str | None = None


class CompanyResponse(BaseModel):
    id: uuid.UUID
    name: str
    domain: str | None
    industry: str | None
    size: CompanySize | None
    phone: str | None
    email: str | None
    website: str | None
    country: str | None
    city: str | None
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Lead ──────────────────────────────────────────────────────────────────────
class LeadCreate(BaseModel):
    title: str = Field(..., max_length=255)
    description: str | None = None
    customer_id: uuid.UUID
    assigned_to: uuid.UUID | None = None
    stage_id: uuid.UUID | None = None
    status: LeadStatus = LeadStatus.NEW
    priority: LeadPriority = LeadPriority.MEDIUM
    source: LeadSource = LeadSource.WHATSAPP
    estimated_value: float | None = None
    probability: float | None = Field(None, ge=0, le=100)
    expected_close_date: str | None = None
    custom_fields: dict | None = None


class LeadUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    assigned_to: uuid.UUID | None = None
    stage_id: uuid.UUID | None = None
    status: LeadStatus | None = None
    priority: LeadPriority | None = None
    estimated_value: float | None = None
    probability: float | None = None
    expected_close_date: str | None = None
    lost_reason: str | None = None
    custom_fields: dict | None = None


class LeadResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    customer_id: uuid.UUID
    assigned_to: uuid.UUID | None
    stage_id: uuid.UUID | None
    status: LeadStatus
    priority: LeadPriority
    source: LeadSource
    estimated_value: float | None
    probability: float | None
    lead_score: int
    buying_intent: str | None
    purchase_probability: float | None
    urgency: str | None
    lost_reason: str | None
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Product ───────────────────────────────────────────────────────────────────
class ProductCreate(BaseModel):
    name: str = Field(..., max_length=255)
    sku: str | None = None
    description: str | None = None
    category: str | None = None
    unit: str | None = None
    price: float = Field(..., ge=0)
    cost: float | None = None
    tax_rate: float = 0.0
    discount: float = 0.0
    stock_quantity: int = 0


class ProductUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    category: str | None = None
    price: float | None = None
    cost: float | None = None
    tax_rate: float | None = None
    discount: float | None = None
    stock_quantity: int | None = None


class ProductResponse(BaseModel):
    id: uuid.UUID
    name: str
    sku: str | None
    description: str | None
    category: str | None
    price: float
    tax_rate: float
    discount: float
    stock_quantity: int
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Order ─────────────────────────────────────────────────────────────────────
class OrderItemCreate(BaseModel):
    product_id: uuid.UUID
    quantity: int = Field(..., ge=1)
    unit_price: float | None = None  # if None, use product price
    discount: float = 0.0


class OrderCreate(BaseModel):
    customer_id: uuid.UUID
    items: list[OrderItemCreate]
    currency: str = "USD"
    shipping_amount: float = 0.0
    discount_amount: float = 0.0
    shipping_address: str | None = None
    billing_address: str | None = None
    notes: str | None = None


class OrderResponse(BaseModel):
    id: uuid.UUID
    order_number: str
    customer_id: uuid.UUID
    status: OrderStatus
    payment_status: PaymentStatus
    subtotal: float
    tax_amount: float
    discount_amount: float
    shipping_amount: float
    total_amount: float
    currency: str
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Appointment ───────────────────────────────────────────────────────────────
class AppointmentCreate(BaseModel):
    title: str = Field(..., max_length=255)
    description: str | None = None
    appointment_type: AppointmentType = AppointmentType.CALL
    customer_id: uuid.UUID
    assigned_to: uuid.UUID | None = None
    start_time: datetime
    end_time: datetime
    timezone: str = "UTC"
    location: str | None = None
    meeting_url: str | None = None
    reminder_minutes_before: int = 30


class AppointmentUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: AppointmentStatus | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    location: str | None = None
    meeting_url: str | None = None
    cancellation_reason: str | None = None
    notes: str | None = None


class AppointmentResponse(BaseModel):
    id: uuid.UUID
    title: str
    appointment_type: AppointmentType
    status: AppointmentStatus
    customer_id: uuid.UUID
    assigned_to: uuid.UUID | None
    start_time: datetime
    end_time: datetime
    timezone: str
    location: str | None
    meeting_url: str | None
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Task ──────────────────────────────────────────────────────────────────────
class TaskCreate(BaseModel):
    title: str = Field(..., max_length=255)
    description: str | None = None
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    assigned_to: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None
    lead_id: uuid.UUID | None = None
    due_date: datetime | None = None
    estimated_hours: float | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    assigned_to: uuid.UUID | None = None
    due_date: datetime | None = None
    estimated_hours: float | None = None
    actual_hours: float | None = None
    notes: str | None = None


class TaskResponse(BaseModel):
    id: uuid.UUID
    title: str
    status: TaskStatus
    priority: TaskPriority
    assigned_to: uuid.UUID | None
    customer_id: uuid.UUID | None
    due_date: datetime | None
    completed_at: datetime | None
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Campaign ──────────────────────────────────────────────────────────────────
class CampaignCreate(BaseModel):
    name: str = Field(..., max_length=255)
    description: str | None = None
    campaign_type: CampaignType = CampaignType.WHATSAPP
    message_template: str
    whatsapp_template_name: str | None = None
    subject: str | None = None
    scheduled_at: datetime | None = None
    audience_filters: dict | None = None


class CampaignUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    message_template: str | None = None
    scheduled_at: datetime | None = None
    status: CampaignStatus | None = None


class CampaignResponse(BaseModel):
    id: uuid.UUID
    name: str
    campaign_type: CampaignType
    status: CampaignStatus
    total_recipients: int
    sent_count: int
    delivered_count: int
    read_count: int
    failed_count: int
    scheduled_at: datetime | None
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Ticket ────────────────────────────────────────────────────────────────────
class TicketCreate(BaseModel):
    subject: str = Field(..., max_length=255)
    description: str
    customer_id: uuid.UUID
    priority: TicketPriority = TicketPriority.MEDIUM
    category: str | None = None


class TicketUpdate(BaseModel):
    subject: str | None = None
    status: TicketStatus | None = None
    priority: TicketPriority | None = None
    assigned_to: uuid.UUID | None = None
    category: str | None = None
    resolution_notes: str | None = None
    satisfaction_rating: int | None = Field(None, ge=1, le=5)


class TicketResponse(BaseModel):
    id: uuid.UUID
    ticket_number: str
    subject: str
    customer_id: uuid.UUID
    assigned_to: uuid.UUID | None
    status: TicketStatus
    priority: TicketPriority
    category: str | None
    created_at: datetime
    resolved_at: datetime | None
    model_config = {"from_attributes": True}


# ── Note ─────────────────────────────────────────────────────────────────────
class NoteCreate(BaseModel):
    customer_id: uuid.UUID
    title: str | None = None
    content: str
    lead_id: uuid.UUID | None = None
    is_pinned: bool = False


class NoteResponse(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    title: str | None
    content: str
    is_pinned: bool
    is_ai_generated: bool
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Activity ──────────────────────────────────────────────────────────────────
class ActivityResponse(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    activity_type: ActivityType
    title: str
    description: str | None
    entity_type: str | None
    entity_id: uuid.UUID | None
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Notification ──────────────────────────────────────────────────────────────
class NotificationResponse(BaseModel):
    id: uuid.UUID
    notification_type: NotificationType
    title: str
    body: str
    is_read: bool
    read_at: datetime | None
    action_url: str | None
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Follow-up ─────────────────────────────────────────────────────────────────
class FollowUpCreate(BaseModel):
    customer_id: uuid.UUID
    subject: str = Field(..., max_length=255)
    message: str | None = None
    follow_up_type: FollowUpType = FollowUpType.WHATSAPP
    scheduled_at: datetime
    lead_id: uuid.UUID | None = None


class FollowUpResponse(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    subject: str
    follow_up_type: FollowUpType
    status: FollowUpStatus
    scheduled_at: datetime
    sent_at: datetime | None
    ai_generated: bool
    created_at: datetime
    model_config = {"from_attributes": True}
