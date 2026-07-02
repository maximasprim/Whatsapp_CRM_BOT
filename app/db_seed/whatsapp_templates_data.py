from __future__ import annotations

"""Default WhatsApp message templates. These mirror Meta-approved template structures
and should be submitted/synced to the WhatsApp Business Manager separately —
this seed data just creates local DB records for reference and selection in campaigns."""

DEFAULT_WHATSAPP_TEMPLATES = [
    {
        "name": "welcome_message",
        "language": "en",
        "category": "MARKETING",
        "status": "approved",
        "body": "Hi {{1}}! Welcome to {{2}}. We're excited to help you. Reply anytime with questions.",
        "footer": "Reply STOP to unsubscribe.",
    },
    {
        "name": "appointment_reminder",
        "language": "en",
        "category": "UTILITY",
        "status": "approved",
        "body": "Reminder: your appointment '{{1}}' is scheduled for {{2}}. Reply CONFIRM or RESCHEDULE.",
        "footer": None,
    },
    {
        "name": "order_confirmation",
        "language": "en",
        "category": "UTILITY",
        "status": "approved",
        "body": "Order {{1}} confirmed! Total: {{2}}. We'll notify you when it ships.",
        "footer": None,
    },
    {
        "name": "abandoned_lead_followup",
        "language": "en",
        "category": "MARKETING",
        "status": "approved",
        "body": "Hi {{1}}, just checking in — still interested in {{2}}? Happy to answer any questions.",
        "footer": "Reply STOP to unsubscribe.",
    },
]
