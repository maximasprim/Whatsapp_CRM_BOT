"""Add multi-tenancy — tenants table and tenant_id to all models

Revision ID: 0002_multitenancy
Revises: 0001_initial
Create Date: 2026-08-07
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_multitenancy"
down_revision = "80779d254241"
branch_labels = None
depends_on = None

DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"

# Tables that need tenant_id added
TENANT_TABLES = [
    "users",
    "customers",
    "companies",
    "leads",
    "products",
    "orders",
    "appointments",
    "tasks",
    "follow_ups",
    "notes",
    "campaigns",
    "support_tickets",
    "tags",
    "activities",
    "notifications",
    "conversations",
    "whatsapp_templates",
    "knowledge_documents",
]


def upgrade() -> None:
    # ── 1. Create tenants table ───────────────────────────────────────────────
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("domain", sa.String(255), nullable=True, unique=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("plan", sa.String(50), nullable=False, server_default="starter"),
        sa.Column("logo_url", sa.String(500), nullable=True),
        sa.Column("primary_color", sa.String(20), nullable=True,
                  server_default="#f97316"),
        sa.Column("business_description", sa.Text, nullable=True),
        sa.Column("website", sa.String(255), nullable=True),
        sa.Column("country", sa.String(100), nullable=True),
        sa.Column("timezone", sa.String(100), nullable=False,
                  server_default="UTC"),
        # WhatsApp credentials
        sa.Column("whatsapp_phone_number_id", sa.String(100), nullable=True),
        sa.Column("whatsapp_access_token", sa.Text, nullable=True),
        sa.Column("whatsapp_business_account_id", sa.String(100), nullable=True),
        sa.Column("whatsapp_webhook_verify_token", sa.String(255), nullable=True),
        sa.Column("whatsapp_app_secret", sa.Text, nullable=True),
        sa.Column("whatsapp_phone_number", sa.String(20), nullable=True),
        # AI settings
        sa.Column("ai_provider", sa.String(50), nullable=False,
                  server_default="gemini"),
        sa.Column("ai_api_key", sa.Text, nullable=True),
        sa.Column("ai_model", sa.String(100), nullable=True),
        # Plan limits
        sa.Column("max_users", sa.Integer, nullable=False, server_default="5"),
        sa.Column("max_customers", sa.Integer, nullable=False,
                  server_default="500"),
        sa.Column("max_messages_per_month", sa.Integer, nullable=False,
                  server_default="1000"),
        sa.Column("max_ai_calls_per_month", sa.Integer, nullable=False,
                  server_default="500"),
        sa.Column("custom_settings", postgresql.JSON, nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"], unique=True)
    op.create_index("ix_tenants_domain", "tenants", ["domain"], unique=True)

    # ── 2. Insert default tenant for existing data ────────────────────────────
    op.execute(f"""
        INSERT INTO tenants (
            id, name, slug, is_active, plan,
            primary_color, timezone,
            max_users, max_customers,
            max_messages_per_month, max_ai_calls_per_month
        ) VALUES (
            '{DEFAULT_TENANT_ID}',
            'Default Business',
            'default',
            true,
            'enterprise',
            '#f97316',
            'UTC',
            9999, 999999, 999999, 999999
        )
    """)

    # ── 3. Add tenant_id to all tables ────────────────────────────────────────
    for table in TENANT_TABLES:
        # Add column as nullable first
        op.add_column(
            table,
            sa.Column(
                "tenant_id",
                postgresql.UUID(as_uuid=True),
                nullable=True,
            ),
        )
        # Set all existing rows to default tenant
        op.execute(f"""
            UPDATE {table}
            SET tenant_id = '{DEFAULT_TENANT_ID}'
            WHERE tenant_id IS NULL
        """)
        # Now make it non-nullable
        op.alter_column(table, "tenant_id", nullable=False)
        # Add foreign key
        op.create_foreign_key(
            f"fk_{table}_tenant_id",
            table,
            "tenants",
            ["tenant_id"],
            ["id"],
            ondelete="CASCADE",
        )
        # Add index for performance
        op.create_index(
            f"ix_{table}_tenant_id",
            table,
            ["tenant_id"],
        )

    # ── 4. Add tenant_id to WhatsApp webhook route ────────────────────────────
    # Update the whatsapp_templates table
    op.add_column(
        "conversation_summaries",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.execute(f"""
        UPDATE conversation_summaries
        SET tenant_id = '{DEFAULT_TENANT_ID}'
        WHERE tenant_id IS NULL
    """)
    op.alter_column("conversation_summaries", "tenant_id", nullable=False)
    op.create_foreign_key(
        "fk_conversation_summaries_tenant_id",
        "conversation_summaries",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    # Remove tenant_id from all tables
    for table in TENANT_TABLES + ["conversation_summaries"]:
        op.drop_constraint(f"fk_{table}_tenant_id", table, type_="foreignkey")
        op.drop_index(f"ix_{table}_tenant_id", table_name=table)
        op.drop_column(table, "tenant_id")

    # Drop tenants table
    op.drop_index("ix_tenants_domain", table_name="tenants")
    op.drop_index("ix_tenants_slug", table_name="tenants")
    op.drop_table("tenants")
