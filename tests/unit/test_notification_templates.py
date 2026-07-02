from __future__ import annotations

import pytest

from app.notifications.templates.registry import render_subject, render_template


class TestAppointmentConfirmationTemplate:
    def setup_method(self):
        self.ctx = {
            "first_name": "Maxwell",
            "appointment_title": "Product Demo",
            "appointment_time": "Monday at 14:00",
            "location": "Nairobi Office",
            "meeting_url": "",
        }

    def test_whatsapp_body_contains_title_and_time(self):
        body = render_template("appointment_confirmation", "whatsapp", self.ctx)
        assert "Product Demo" in body
        assert "Monday at 14:00" in body

    def test_email_body_contains_customer_name(self):
        body = render_template("appointment_confirmation", "email", self.ctx)
        assert "Maxwell" in body

    def test_subject_contains_appointment_title(self):
        subject = render_subject("appointment_confirmation", self.ctx)
        assert "Product Demo" in subject

    def test_meeting_url_shown_when_present(self):
        ctx = {**self.ctx, "meeting_url": "https://meet.google.com/abc-def"}
        body = render_template("appointment_confirmation", "whatsapp", ctx)
        assert "https://meet.google.com/abc-def" in body

    def test_meeting_url_omitted_when_empty(self):
        body = render_template("appointment_confirmation", "whatsapp", self.ctx)
        assert "meet.google.com" not in body


class TestOrderConfirmationTemplate:
    def setup_method(self):
        self.ctx = {
            "first_name": "Jane",
            "order_number": "ORD-XY3Z99",
            "currency": "KES",
            "total_amount": "4500.00",
        }

    def test_sms_body_includes_order_number_and_total(self):
        body = render_template("order_confirmation", "sms", self.ctx)
        assert "ORD-XY3Z99" in body
        assert "4500.00" in body
        assert "KES" in body

    def test_whatsapp_body_includes_emoji_and_details(self):
        body = render_template("order_confirmation", "whatsapp", self.ctx)
        assert "🎉" in body
        assert "ORD-XY3Z99" in body


class TestTicketCreatedTemplate:
    def test_all_channels_include_ticket_number(self):
        ctx = {"first_name": "Bob", "ticket_number": "TKT-001234", "subject": "Cannot log in"}
        for channel in ("email", "sms", "whatsapp"):
            body = render_template("ticket_created", channel, ctx)
            assert "TKT-001234" in body, f"Ticket number missing in {channel}"


class TestPasswordResetTemplate:
    def test_email_body_includes_reset_url(self):
        ctx = {"reset_url": "https://app.example.com/reset?token=abc123"}
        body = render_template("password_reset", "email", ctx)
        assert "https://app.example.com/reset?token=abc123" in body


class TestUnknownTemplate:
    def test_unknown_template_key_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown notification template"):
            render_template("nonexistent_template", "email", {})

    def test_unknown_channel_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown channel"):
            render_template("welcome", "telegram", {"first_name": "A", "company_name": "B"})
