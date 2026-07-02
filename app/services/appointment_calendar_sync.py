from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException, NotFoundException
from app.core.logging import get_logger
from app.integrations.google_calendar.client import GoogleCalendarClient
from app.models.appointment import Appointment, AppointmentStatus
from app.repositories.calendar_credential import CalendarCredentialRepository
from app.repositories.crm import AppointmentRepository, CustomerRepository
from app.schemas.crm import AppointmentCreate, AppointmentUpdate

logger = get_logger(__name__)


class AppointmentCalendarSyncService:
    """Wraps appointment booking with optional Google Calendar two-way sync.
    If the assigned agent hasn't connected a calendar, appointments are still
    created in the CRM normally — calendar sync is purely additive."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.appt_repo = AppointmentRepository(session)
        self.cust_repo = CustomerRepository(session)
        self.cred_repo = CalendarCredentialRepository(session)

    async def is_calendar_connected(self, user_id: uuid.UUID) -> bool:
        cred = await self.cred_repo.get_by_user(user_id)
        return cred is not None

    async def check_slot_availability(
        self, agent_id: uuid.UUID, start_time: datetime, end_time: datetime
    ) -> bool:
        """Checks both internal CRM appointments and (if connected) Google Calendar
        for conflicting bookings."""
        # Internal DB check first — cheap and always available
        from sqlalchemy import and_, select
        stmt = select(Appointment).where(
            and_(
                Appointment.assigned_to == agent_id,
                Appointment.status.notin_([AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW]),
                Appointment.start_time < end_time,
                Appointment.end_time > start_time,
            )
        )
        result = await self.session.execute(stmt)
        if result.scalars().first() is not None:
            return False

        # Google Calendar check, if connected
        if await self.is_calendar_connected(agent_id):
            client = GoogleCalendarClient(self.session, agent_id)
            try:
                return await client.check_availability(start_time, end_time)
            except Exception as exc:
                logger.warning("Calendar availability check failed, falling back to CRM-only", error=str(exc))

        return True

    async def book_appointment(
        self, data: AppointmentCreate, created_by: uuid.UUID | None = None
    ) -> Appointment:
        if data.assigned_to:
            is_free = await self.check_slot_availability(data.assigned_to, data.start_time, data.end_time)
            if not is_free:
                raise ConflictException("This time slot is already booked.")

        appt = await self.appt_repo.create(**data.model_dump())

        if data.assigned_to and await self.is_calendar_connected(data.assigned_to):
            try:
                customer = await self.cust_repo.get_by_id(data.customer_id)
                client = GoogleCalendarClient(self.session, data.assigned_to)
                event = await client.create_event(
                    summary=data.title,
                    description=(data.description or "") + f"\n\nCustomer: {customer.full_name if customer else ''} ({customer.phone if customer else ''})",
                    start_time=data.start_time,
                    end_time=data.end_time,
                    timezone=data.timezone,
                    location=data.location,
                    attendee_emails=[customer.email] if customer and customer.email else None,
                    add_meet_link=data.appointment_type == "video_call",
                )
                appt.google_event_id = event.get("id")
                if event.get("hangoutLink"):
                    appt.meeting_url = event["hangoutLink"]
                self.session.add(appt)
                await self.session.flush()
            except Exception as exc:
                logger.error("Failed to sync appointment to Google Calendar", error=str(exc), appt_id=str(appt.id))

        try:
            customer = await self.cust_repo.get_by_id(data.customer_id)
            if customer and customer.phone:
                from app.notifications.engine import NotificationChannel, NotificationEngine
                engine = NotificationEngine(self.session)
                await engine.send_templated(
                    template_key="appointment_confirmation",
                    context={
                        "first_name": customer.first_name,
                        "appointment_title": appt.title,
                        "appointment_time": appt.start_time.strftime("%A, %B %d at %H:%M"),
                        "location": appt.location or "",
                        "meeting_url": appt.meeting_url or "",
                    },
                    channels=[NotificationChannel.WHATSAPP, NotificationChannel.EMAIL] if customer.email else [NotificationChannel.WHATSAPP],
                    whatsapp_to=customer.phone,
                    email_to=customer.email,
                )
        except Exception as exc:
            logger.error("Failed to send appointment confirmation notification", error=str(exc))

        return appt

    async def reschedule_appointment(
        self, appointment_id: uuid.UUID, new_start: datetime, new_end: datetime
    ) -> Appointment:
        appt = await self.appt_repo.get_by_id_or_raise(appointment_id)

        if appt.assigned_to:
            is_free = await self.check_slot_availability(appt.assigned_to, new_start, new_end)
            if not is_free:
                raise ConflictException("The new time slot is already booked.")

        old_status = appt.status
        appt = await self.appt_repo.update(
            appt, start_time=new_start, end_time=new_end,
            status=AppointmentStatus.RESCHEDULED, reminder_sent=False,
        )

        if appt.google_event_id and appt.assigned_to:
            try:
                client = GoogleCalendarClient(self.session, appt.assigned_to)
                await client.update_event(
                    appt.google_event_id, start_time=new_start, end_time=new_end, timezone=appt.timezone,
                )
            except Exception as exc:
                logger.error("Failed to update Google Calendar event", error=str(exc), appt_id=str(appointment_id))

        return appt

    async def cancel_appointment(self, appointment_id: uuid.UUID, reason: str | None = None) -> Appointment:
        appt = await self.appt_repo.get_by_id_or_raise(appointment_id)
        appt = await self.appt_repo.update(
            appt, status=AppointmentStatus.CANCELLED, cancellation_reason=reason,
        )

        if appt.google_event_id and appt.assigned_to:
            try:
                client = GoogleCalendarClient(self.session, appt.assigned_to)
                await client.delete_event(appt.google_event_id)
            except Exception as exc:
                logger.error("Failed to delete Google Calendar event", error=str(exc), appt_id=str(appointment_id))

        return appt

    async def get_available_slots(
        self,
        agent_id: uuid.UUID,
        date: datetime,
        slot_duration_minutes: int = 30,
        work_start_hour: int = 9,
        work_end_hour: int = 17,
    ) -> list[dict]:
        """Generate available time slots for a given day, checking both CRM and Calendar."""
        day_start = date.replace(hour=work_start_hour, minute=0, second=0, microsecond=0)
        day_end = date.replace(hour=work_end_hour, minute=0, second=0, microsecond=0)

        slots = []
        current = day_start
        while current + timedelta(minutes=slot_duration_minutes) <= day_end:
            slot_end = current + timedelta(minutes=slot_duration_minutes)
            is_free = await self.check_slot_availability(agent_id, current, slot_end)
            slots.append({
                "start": current.isoformat(),
                "end": slot_end.isoformat(),
                "available": is_free,
            })
            current = slot_end

        return slots
