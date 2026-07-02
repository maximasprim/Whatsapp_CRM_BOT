from __future__ import annotations

"""Default permission catalogue: (resource, action, description) tuples.
Actions follow CRUD convention: create, read, update, delete, plus 'manage' for full control."""

RESOURCES = [
    "users", "roles", "permissions",
    "customers", "companies", "leads", "products", "orders", "payments",
    "appointments", "tasks", "followups", "notes", "campaigns", "tickets",
    "tags", "activities", "notifications", "analytics", "settings",
    "conversations", "whatsapp", "ai", "knowledge_base", "calendar",
]

ACTIONS = ["create", "read", "update", "delete", "manage"]

ACTION_DESCRIPTIONS = {
    "create": "Create new {resource}",
    "read": "View {resource}",
    "update": "Edit existing {resource}",
    "delete": "Delete {resource}",
    "manage": "Full administrative control over {resource}",
}


def generate_permission_catalogue() -> list[dict]:
    permissions = []
    for resource in RESOURCES:
        for action in ACTIONS:
            permissions.append({
                "name": f"{resource}.{action}".replace("_", " ").title(),
                "codename": f"{resource}_{action}",
                "description": ACTION_DESCRIPTIONS[action].format(resource=resource.replace("_", " ")),
                "resource": resource,
                "action": action,
            })
    return permissions
