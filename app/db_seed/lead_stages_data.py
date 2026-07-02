from __future__ import annotations

"""Default lead pipeline stages, in display order."""

DEFAULT_LEAD_STAGES = [
    {"name": "New", "description": "Lead has just entered the pipeline.", "order": 0, "color": "#94A3B8", "is_won": False, "is_lost": False},
    {"name": "Contacted", "description": "Initial outreach has been made.", "order": 1, "color": "#60A5FA", "is_won": False, "is_lost": False},
    {"name": "Qualified", "description": "Lead meets ICP and has confirmed interest.", "order": 2, "color": "#818CF8", "is_won": False, "is_lost": False},
    {"name": "Proposal Sent", "description": "A formal proposal or quote has been shared.", "order": 3, "color": "#FBBF24", "is_won": False, "is_lost": False},
    {"name": "Negotiation", "description": "Actively discussing terms, pricing, or scope.", "order": 4, "color": "#FB923C", "is_won": False, "is_lost": False},
    {"name": "Won", "description": "Deal closed successfully.", "order": 5, "color": "#34D399", "is_won": True, "is_lost": False},
    {"name": "Lost", "description": "Deal did not close.", "order": 6, "color": "#F87171", "is_won": False, "is_lost": True},
]
