#!/usr/bin/env python3
"""
CLI entry point for seeding the database with default roles, permissions,
lead pipeline stages, WhatsApp templates, and an optional superuser.

Usage:
    python scripts/seed_db.py

Environment variables:
    SEED_SUPERUSER_EMAIL       (default: admin@example.com)
    SEED_SUPERUSER_PASSWORD    (required to create a superuser; skipped if unset)
    SEED_SUPERUSER_USERNAME    (default: admin)
    SEED_SUPERUSER_FIRST_NAME  (default: System)
    SEED_SUPERUSER_LAST_NAME   (default: Administrator)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db_seed.seeder import main

if __name__ == "__main__":
    main()
