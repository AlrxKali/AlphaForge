"""Supabase client factories.

Two flavors:
  * ``service_client`` bypasses row-level security (used by the worker and for
    storage operations / signed URLs).
  * ``user_client`` is scoped to a caller's JWT, so PostgREST applies RLS and
    the user only ever sees their own rows. Used by request handlers.
"""

from __future__ import annotations

from supabase import Client, create_client

from alphaforge_api.settings import get_settings


def service_client() -> Client:
    s = get_settings()
    return create_client(s.supabase_url, s.supabase_service_role_key)


def user_client(access_token: str) -> Client:
    s = get_settings()
    client = create_client(s.supabase_url, s.supabase_anon_key)
    # Attach the caller's token so RLS sees auth.uid() == the user.
    client.postgrest.auth(access_token)
    return client
