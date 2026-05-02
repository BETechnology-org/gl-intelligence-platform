"""Singleton Supabase service-role client.

Reads SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY from env. Returns None
if either is missing — callers must check via `supabase_available()`
and fall back to BigQuery / module-level state for backward compat.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

log = logging.getLogger("persistence.supabase")

_client: Optional[Any] = None
_init_attempted = False


def supabase_available() -> bool:
    """True when SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY are set."""
    return bool(os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))


def get_supabase() -> Optional[Any]:
    """Return a singleton Supabase service-role client, or None if unconfigured."""
    global _client, _init_attempted
    if _client is not None:
        return _client
    if _init_attempted:
        return None
    _init_attempted = True

    if not supabase_available():
        log.info("Supabase env vars not set — running with legacy in-memory state")
        return None

    try:
        from supabase import create_client  # type: ignore
        _client = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SERVICE_ROLE_KEY"],
        )
        log.info("Supabase client initialized (service role)")
        return _client
    except ImportError:
        log.warning("supabase Python package not installed — falling back to in-memory state")
        return None
    except Exception as e:  # noqa: BLE001
        log.error("Supabase client init failed: %s — falling back to in-memory state", e)
        return None


# Default company id used when the legacy Flask routes don't send one.
# This is the demo company seeded by migrations/supabase/0001 — matches
# the C006 fixture the legacy agents already operate on.
DEFAULT_COMPANY_ID = os.environ.get(
    "DEFAULT_COMPANY_ID",
    "00000000-0000-0000-0000-000000000c06",
)
