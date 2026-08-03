# app/models/__init__.py
from app.models.customer import Customer, CustomerStatus, CustomerGender
from app.models.conversation import (
    Conversation,
    ConversationMessage,
    MessageAttachment,
    ConversationStatus,
    MessageDirection,
    MessageType,
)
from app.models.company import Company
from app.models.lead import Lead
from app.models.activity import Activity
from app.models.note import Note
from app.models.customer import Customer
# add any other model modules you have — campaigns, notifications, etc.

__all__ = [
    "Customer",
    "Conversation",
    "ConversationMessage",
    "MessageAttachment",
    "Company",
    "Lead",
    "Activity",
    "Note",
    "User",
]