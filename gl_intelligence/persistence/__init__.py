"""Supabase-backed persistence layer.

Replaces the module-level Python lists in the legacy classifier agents
(see tax_classifier_agent._pending_tax_mappings — lost on Cloud Run
restart) with durable Postgres storage. The Flask routes that the
legacy /app HTML UI calls don't change — they just get a real DB
backing them now.
"""

from .supabase_client import get_supabase, supabase_available
from .audit import write_audit_event

__all__ = ["get_supabase", "supabase_available", "write_audit_event"]
