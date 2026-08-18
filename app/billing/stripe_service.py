"""
Stripe billing service — handles subscriptions, checkouts, and webhooks.
Install stripe: pip install stripe
"""
from __future__ import annotations

import uuid
from typing import Any

import stripe
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.billing import Invoice, Subscription
from app.models.tenant import Tenant

logger = get_logger(__name__)

# Plan configuration — prices in cents
PLANS = {
    "starter": {
        "name": "Starter",
        "price_monthly": 0,       # Free
        "stripe_price_id": None,  # No Stripe needed for free
        "max_users": 5,
        "max_customers": 500,
        "max_messages_per_month": 1000,
        "max_ai_calls_per_month": 500,
    },
    "pro": {
        "name": "Pro",
        "price_monthly": 2900,    # $29/month in cents
        "stripe_price_id": "price_1U5gBQRswI1Rz1KkzsmHWZ8X",  # Set your Stripe price ID
        "max_users": 20,
        "max_customers": 5000,
        "max_messages_per_month": 10000,
        "max_ai_calls_per_month": 5000,
    },
    "enterprise": {
        "name": "Enterprise",
        "price_monthly": 9900,    # $99/month in cents
        "stripe_price_id": "price_1U5gD3RswI1Rz1KkbvHKSptm",
        "max_users": 9999,
        "max_customers": 999999,
        "max_messages_per_month": 999999,
        "max_ai_calls_per_month": 999999,
    },
}


class StripeService:
    def __init__(self) -> None:
        stripe.api_key = getattr(settings, "STRIPE_SECRET_KEY", "")

    async def create_checkout_session(
        self,
        tenant: Tenant,
        plan: str,
        success_url: str,
        cancel_url: str,
    ) -> str:
        """Create a Stripe checkout session for plan upgrade."""
        plan_config = PLANS.get(plan)
        if not plan_config or not plan_config["stripe_price_id"]:
            raise ValueError(f"Invalid plan or free plan: {plan}")

        # Get or create Stripe customer
        customer_id = await self._get_or_create_customer(tenant)

        session = stripe.checkout.Session.create(
            customer=customer_id,
            mode="subscription",
            line_items=[{
                "price": plan_config["stripe_price_id"],
                "quantity": 1,
            }],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "tenant_id": str(tenant.id),
                "tenant_slug": tenant.slug,
                "plan": plan,
            },
            subscription_data={
                "metadata": {
                    "tenant_id": str(tenant.id),
                    "plan": plan,
                }
            },
        )
        return session.url

    async def create_billing_portal_session(
        self,
        tenant: Tenant,
        return_url: str,
    ) -> str:
        """Create a Stripe billing portal session for managing subscription."""
        customer_id = await self._get_or_create_customer(tenant)
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
        )
        return session.url

    async def _get_or_create_customer(self, tenant: Tenant) -> str:
        """Get existing Stripe customer or create new one."""
        # Check if tenant already has a Stripe customer
        from sqlalchemy import select
        # This would normally query the subscription table
        # Simplified for this example

        customer = stripe.Customer.create(
            name=tenant.name,
            metadata={
                "tenant_id": str(tenant.id),
                "tenant_slug": tenant.slug,
            },
        )
        return customer.id

    async def handle_webhook(
        self,
        payload: bytes,
        signature: str,
        session: AsyncSession,
    ) -> dict:
        """Handle Stripe webhook events."""
        webhook_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", "")

        try:
            event = stripe.Webhook.construct_event(
                payload, signature, webhook_secret
            )
        except stripe.error.SignatureVerificationError:
            logger.error("Invalid Stripe webhook signature")
            return {"error": "invalid signature"}

        event_type = event["type"]
        logger.info("Stripe webhook received", event_type=event_type)

        if event_type == "checkout.session.completed":
            await self._handle_checkout_completed(event["data"]["object"], session)

        elif event_type == "customer.subscription.updated":
            await self._handle_subscription_updated(event["data"]["object"], session)

        elif event_type == "customer.subscription.deleted":
            await self._handle_subscription_cancelled(event["data"]["object"], session)

        elif event_type == "invoice.payment_succeeded":
            await self._handle_invoice_paid(event["data"]["object"], session)

        elif event_type == "invoice.payment_failed":
            await self._handle_invoice_failed(event["data"]["object"], session)

        return {"received": True}

    async def _handle_checkout_completed(
        self, session_obj: dict, db: AsyncSession
    ) -> None:
        """Activate subscription after successful checkout."""
        metadata = session_obj.get("metadata", {})
        tenant_id = metadata.get("tenant_id")
        plan = metadata.get("plan")

        if not tenant_id or not plan:
            return

        tenant = await db.get(Tenant, uuid.UUID(tenant_id))
        if not tenant:
            return

        plan_config = PLANS.get(plan, {})

        # Update tenant plan and limits
        tenant.plan = plan
        tenant.max_users = plan_config.get("max_users", 5)
        tenant.max_customers = plan_config.get("max_customers", 500)
        tenant.max_messages_per_month = plan_config.get("max_messages_per_month", 1000)
        tenant.max_ai_calls_per_month = plan_config.get("max_ai_calls_per_month", 500)

        db.add(tenant)

        # Create subscription record
        subscription = Subscription(
            tenant_id=tenant.id,
            plan=plan,
            status="active",
            stripe_customer_id=session_obj.get("customer"),
            stripe_subscription_id=session_obj.get("subscription"),
            max_users=plan_config.get("max_users", 5),
            max_customers=plan_config.get("max_customers", 500),
            max_messages_per_month=plan_config.get("max_messages_per_month", 1000),
            max_ai_calls_per_month=plan_config.get("max_ai_calls_per_month", 500),
        )
        db.add(subscription)
        await db.flush()

        logger.info(
            "Subscription activated",
            tenant_slug=tenant.slug,
            plan=plan,
        )

    async def _handle_subscription_updated(
        self, subscription: dict, db: AsyncSession
    ) -> None:
        metadata = subscription.get("metadata", {})
        tenant_id = metadata.get("tenant_id")
        if not tenant_id:
            return
        tenant = await db.get(Tenant, uuid.UUID(tenant_id))
        if tenant:
            new_status = subscription.get("status", "active")
            logger.info(
                "Subscription updated",
                tenant_slug=tenant.slug,
                status=new_status,
            )

    async def _handle_subscription_cancelled(
        self, subscription: dict, db: AsyncSession
    ) -> None:
        metadata = subscription.get("metadata", {})
        tenant_id = metadata.get("tenant_id")
        if not tenant_id:
            return
        tenant = await db.get(Tenant, uuid.UUID(tenant_id))
        if tenant:
            # Downgrade to starter
            tenant.plan = "starter"
            tenant.max_users = 5
            tenant.max_customers = 500
            tenant.max_messages_per_month = 1000
            tenant.max_ai_calls_per_month = 500
            db.add(tenant)
            await db.flush()
            logger.info("Tenant downgraded to starter", tenant_slug=tenant.slug)

    async def _handle_invoice_paid(
        self, invoice: dict, db: AsyncSession
    ) -> None:
        logger.info("Invoice paid", invoice_id=invoice.get("id"))

    async def _handle_invoice_failed(
        self, invoice: dict, db: AsyncSession
    ) -> None:
        logger.warning("Invoice payment failed", invoice_id=invoice.get("id"))
