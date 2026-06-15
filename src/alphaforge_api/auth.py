"""Authentication: verify the Supabase JWT and expose the caller.

Supabase access tokens may be signed either asymmetrically (ES256 / RS256,
verified against the project JWKS endpoint) or with a shared HS256 secret,
depending on the project. We read the token header to pick the right path, so
both modes work without configuration. The user id comes from the ``sub`` claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import jwt
from fastapi import Header, HTTPException, status

from alphaforge_api.settings import get_settings

_AUDIENCE = "authenticated"
_ASYMMETRIC = {"ES256", "ES384", "ES512", "RS256", "RS384", "RS512"}


@dataclass
class AuthUser:
    id: str
    token: str
    email: str | None = None


@lru_cache
def _jwks_client() -> jwt.PyJWKClient:
    url = get_settings().supabase_url.rstrip("/") + "/auth/v1/.well-known/jwks.json"
    return jwt.PyJWKClient(url)


def _decode(token: str) -> dict:
    alg = jwt.get_unverified_header(token).get("alg", "")
    if alg in _ASYMMETRIC:
        key = _jwks_client().get_signing_key_from_jwt(token).key
        return jwt.decode(token, key, algorithms=[alg], audience=_AUDIENCE)
    # Shared-secret instances (HS256).
    secret = get_settings().supabase_jwt_secret
    return jwt.decode(token, secret, algorithms=["HS256"], audience=_AUDIENCE)


def get_current_user(authorization: str | None = Header(default=None)) -> AuthUser:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Missing or malformed Authorization header"
        )
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = _decode(token)
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid token: {exc}") from exc

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token missing subject")
    return AuthUser(id=sub, token=token, email=payload.get("email"))
