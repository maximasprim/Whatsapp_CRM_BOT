from __future__ import annotations
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB as _PostgresJSONB

JSONB = _PostgresJSONB().with_variant(JSON(), "sqlite")