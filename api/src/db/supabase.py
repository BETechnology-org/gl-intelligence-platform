"""Supabase client factories.

Two clients:
- `get_supabase_admin()` — service-role key, bypasses RLS. Used for agent
  writes, audit log inserts, and the BQ promotion worker. NEVER expose
  this client to user-supplied code.
- `get_supabase_for_user(jwt)` — anon-key client with the user's JWT
  applied. Reads/writes flow through RLS as the authenticated user.
"""

from __future__ import annotations

from functools import lru_cache

from supabase import Client, create_client

from ..config import settings


@lru_cache(maxsize=1)
def get_supabase_admin() -> Client:
    """Service-role client. Singleton — reuses connection pool."""
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def get_supabase_for_user(access_token: str) -> Client:
    """Anon-key client with the user's JWT applied (RLS enforced)."""
    if not settings.supabase_anon_key:
        raise RuntimeError("SUPABASE_ANON_KEY required for per-user clients")
    client = create_client(settings.supabase_url, settings.supabase_anon_key)
    # Apply the bearer token so postgrest sends it on every request.
    client.postgrest.auth(access_token)
    return client
