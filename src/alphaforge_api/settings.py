"""Service configuration, sourced from environment / .env.

Local-dev defaults point at the Supabase CLI stack (API on 54321). Secrets are
never committed; see .env.example for the keys to set.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Supabase (local-dev API endpoint by default; Studio is on 54323).
    supabase_url: str = "http://127.0.0.1:54321"
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    supabase_jwt_secret: str = ""

    # Redis / arq
    redis_url: str = "redis://127.0.0.1:6379"

    # Storage buckets
    reports_bucket: str = "reports"
    universes_bucket: str = "universes"

    # Misc
    signed_url_ttl: int = 3600  # seconds for report download links

    # CORS: comma-separated allowed origins (the frontend dev server by default).
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    def allowed_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
