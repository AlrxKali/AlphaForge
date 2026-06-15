"""FastAPI dependencies, isolated so tests can override them with fakes."""

from __future__ import annotations

from fastapi import Depends, Request

from alphaforge_api.auth import AuthUser, get_current_user
from alphaforge_api.db import user_client


def get_user_db(user: AuthUser = Depends(get_current_user)):
    """An RLS-scoped Supabase client for the calling user."""
    return user_client(user.token)


def get_queue(request: Request):
    """The arq pool created at app startup (see main.lifespan)."""
    return request.app.state.arq
