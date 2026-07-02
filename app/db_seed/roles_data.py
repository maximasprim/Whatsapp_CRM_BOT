from __future__ import annotations

"""Default role definitions and which permission codenames each role grants.
'manage' on a resource implies all CRUD actions on that resource — the seeder
expands this when assigning permissions to roles."""

DEFAULT_ROLES = {
    "admin": {
        "description": "Full system access — manages users, roles, and all CRM data.",
        "is_system": True,
        "resources": "*",  # special marker: every permission
    },
    "sales_manager": {
        "description": "Manages the sales pipeline, leads, customers, and team performance.",
        "is_system": True,
        "resources": [
            "customers", "companies", "leads", "products", "orders", "payments",
            "appointments", "tasks", "followups", "notes", "campaigns", "tags",
            "activities", "analytics", "conversations", "whatsapp", "ai", "calendar",
        ],
    },
    "sales_agent": {
        "description": "Works leads, customers, and appointments assigned to them.",
        "is_system": True,
        "resources_partial": {
            "customers": ["create", "read", "update"],
            "companies": ["read"],
            "leads": ["create", "read", "update"],
            "products": ["read"],
            "orders": ["create", "read"],
            "appointments": ["create", "read", "update"],
            "tasks": ["create", "read", "update"],
            "followups": ["create", "read", "update"],
            "notes": ["create", "read"],
            "activities": ["read"],
            "conversations": ["read", "update"],
            "whatsapp": ["read", "create"],
            "ai": ["read", "create"],
            "calendar": ["create", "read", "update"],
        },
    },
    "support_agent": {
        "description": "Handles support tickets and customer conversations.",
        "is_system": True,
        "resources_partial": {
            "customers": ["read", "update"],
            "tickets": ["create", "read", "update"],
            "notes": ["create", "read"],
            "conversations": ["read", "update"],
            "whatsapp": ["read", "create"],
            "ai": ["read"],
            "knowledge_base": ["read"],
            "tasks": ["create", "read", "update"],
        },
    },
    "marketing": {
        "description": "Manages campaigns and customer segmentation.",
        "is_system": True,
        "resources_partial": {
            "customers": ["read"],
            "campaigns": ["create", "read", "update", "delete"],
            "tags": ["create", "read", "update"],
            "analytics": ["read"],
            "whatsapp": ["read"],
        },
    },
    "viewer": {
        "description": "Read-only access across the CRM, for reporting and oversight.",
        "is_system": True,
        "resources_partial": {r: ["read"] for r in [
            "customers", "companies", "leads", "products", "orders",
            "appointments", "tasks", "campaigns", "tickets", "analytics", "conversations",
        ]},
    },
}
