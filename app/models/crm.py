"""
CRM models import hub — imported by Alembic env.py to register all tables.
Keep this file import-only; no logic here.
"""
from app.models.customer import Customer, CustomerStatus, CustomerGender
from app.models.company import Company, CompanySize
from app.models.lead import Lead, LeadStage, LeadStatus, LeadPriority, LeadSource
from app.models.product import Product, ProductStatus
from app.models.order import Order, OrderItem, Payment, OrderStatus, PaymentStatus
from app.models.appointment import Appointment, AppointmentStatus, AppointmentType
from app.models.task import Task, TaskStatus, TaskPriority
from app.models.followup import FollowUp, FollowUpStatus, FollowUpType
from app.models.note import Note
from app.models.campaign import Campaign, CampaignRecipient, CampaignStatus, CampaignType
from app.models.ticket import SupportTicket, TicketMessage, TicketStatus, TicketPriority
from app.models.tag import Tag
from app.models.activity import Activity, ActivityType
from app.models.notification import Notification, NotificationType

__all__ = [
    "Customer", "CustomerStatus", "CustomerGender",
    "Company", "CompanySize",
    "Lead", "LeadStage", "LeadStatus", "LeadPriority", "LeadSource",
    "Product", "ProductStatus",
    "Order", "OrderItem", "Payment", "OrderStatus", "PaymentStatus",
    "Appointment", "AppointmentStatus", "AppointmentType",
    "Task", "TaskStatus", "TaskPriority",
    "FollowUp", "FollowUpStatus", "FollowUpType",
    "Note",
    "Campaign", "CampaignRecipient", "CampaignStatus", "CampaignType",
    "SupportTicket", "TicketMessage", "TicketStatus", "TicketPriority",
    "Tag", "Activity", "ActivityType",
    "Notification", "NotificationType",
]
