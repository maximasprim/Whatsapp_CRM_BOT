from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from jinja2 import Environment, BaseLoader

_env = Environment(loader=BaseLoader(), autoescape=True)


@dataclass
class NotificationTemplate:
    key: str
    subject: str
    email_body: str
    sms_body: str
    whatsapp_body: str


TEMPLATES: dict[str, NotificationTemplate] = {
    "welcome": NotificationTemplate(
        key="welcome",
        subject="Welcome to {{ company_name }}!",
        email_body="""
        <h2>Welcome, {{ first_name }}!</h2>
        <p>Thanks for connecting with {{ company_name }}. We're excited to help you.</p>
        <p>If you have any questions, just reply to this email or message us on WhatsApp.</p>
        """,
        sms_body="Welcome to {{ company_name }}, {{ first_name }}! We're glad you're here.",
        whatsapp_body="Hi {{ first_name }} 👋 Welcome to {{ company_name }}! How can we help you today?",
    ),
    "appointment_confirmation": NotificationTemplate(
        key="appointment_confirmation",
        subject="Appointment Confirmed: {{ appointment_title }}",
        email_body="""
        <h2>Your appointment is confirmed</h2>
        <p>Hi {{ first_name }},</p>
        <p><strong>{{ appointment_title }}</strong> is scheduled for {{ appointment_time }}.</p>
        {% if location %}<p>Location: {{ location }}</p>{% endif %}
        {% if meeting_url %}<p>Join here: <a href="{{ meeting_url }}">{{ meeting_url }}</a></p>{% endif %}
        """,
        sms_body="Confirmed: {{ appointment_title }} at {{ appointment_time }}.{% if location %} Location: {{ location }}{% endif %}",
        whatsapp_body="✅ Your appointment '{{ appointment_title }}' is confirmed for {{ appointment_time }}.{% if meeting_url %} Join: {{ meeting_url }}{% endif %}",
    ),
    "appointment_reminder": NotificationTemplate(
        key="appointment_reminder",
        subject="Reminder: {{ appointment_title }} starting soon",
        email_body="""
        <h2>Appointment reminder</h2>
        <p>Hi {{ first_name }}, this is a reminder that <strong>{{ appointment_title }}</strong> starts at {{ appointment_time }}.</p>
        """,
        sms_body="Reminder: {{ appointment_title }} starts at {{ appointment_time }}.",
        whatsapp_body="⏰ Reminder: '{{ appointment_title }}' starts at {{ appointment_time }}.",
    ),
    "order_confirmation": NotificationTemplate(
        key="order_confirmation",
        subject="Order Confirmed: {{ order_number }}",
        email_body="""
        <h2>Thank you for your order!</h2>
        <p>Hi {{ first_name }},</p>
        <p>Your order <strong>{{ order_number }}</strong> totaling {{ currency }} {{ total_amount }} has been confirmed.</p>
        """,
        sms_body="Order {{ order_number }} confirmed. Total: {{ currency }} {{ total_amount }}.",
        whatsapp_body="🎉 Order {{ order_number }} confirmed! Total: {{ currency }} {{ total_amount }}. Thank you!",
    ),
    "ticket_created": NotificationTemplate(
        key="ticket_created",
        subject="Support Ticket Opened: {{ ticket_number }}",
        email_body="""
        <h2>We've received your request</h2>
        <p>Hi {{ first_name }}, your ticket <strong>{{ ticket_number }}</strong> ({{ subject }}) has been opened. We'll respond shortly.</p>
        """,
        sms_body="Ticket {{ ticket_number }} opened: {{ subject }}. We'll respond soon.",
        whatsapp_body="🎫 Ticket {{ ticket_number }} opened: {{ subject }}. Our team will respond shortly.",
    ),
    "ticket_resolved": NotificationTemplate(
        key="ticket_resolved",
        subject="Ticket Resolved: {{ ticket_number }}",
        email_body="""
        <h2>Your ticket has been resolved</h2>
        <p>Hi {{ first_name }}, ticket <strong>{{ ticket_number }}</strong> has been marked resolved.</p>
        <p>{{ resolution_notes }}</p>
        """,
        sms_body="Ticket {{ ticket_number }} resolved. {{ resolution_notes }}",
        whatsapp_body="✅ Ticket {{ ticket_number }} resolved: {{ resolution_notes }}",
    ),
    "password_reset": NotificationTemplate(
        key="password_reset",
        subject="Reset Your Password",
        email_body="""
        <h2>Password Reset Request</h2>
        <p>Click the link below to reset your password. This link expires in 2 hours.</p>
        <p><a href="{{ reset_url }}">Reset Password</a></p>
        <p>If you didn't request this, you can safely ignore this email.</p>
        """,
        sms_body="Reset your password: {{ reset_url }}",
        whatsapp_body="Reset your password here: {{ reset_url }}",
    ),
    "lead_assigned": NotificationTemplate(
        key="lead_assigned",
        subject="New Lead Assigned: {{ lead_title }}",
        email_body="""
        <h2>New lead assigned to you</h2>
        <p><strong>{{ lead_title }}</strong> has been assigned to you. Score: {{ lead_score }}/100.</p>
        """,
        sms_body="New lead assigned: {{ lead_title }} (score {{ lead_score }}).",
        whatsapp_body="📋 New lead assigned: {{ lead_title }} (score: {{ lead_score }}/100)",
    ),
}


def render_template(template_key: str, channel: str, context: dict[str, Any]) -> str:
    """Render a notification template for a given channel (email/sms/whatsapp)."""
    template = TEMPLATES.get(template_key)
    if not template:
        raise ValueError(f"Unknown notification template: {template_key}")

    body_map = {
        "email": template.email_body,
        "sms": template.sms_body,
        "whatsapp": template.whatsapp_body,
    }
    raw = body_map.get(channel)
    if raw is None:
        raise ValueError(f"Unknown channel: {channel}")

    return _env.from_string(raw).render(**context).strip()


def render_subject(template_key: str, context: dict[str, Any]) -> str:
    template = TEMPLATES.get(template_key)
    if not template:
        raise ValueError(f"Unknown notification template: {template_key}")
    return _env.from_string(template.subject).render(**context).strip()
