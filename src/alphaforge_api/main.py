"""FastAPI application wiring.

Run with:  uvicorn alphaforge_api.main:app   (or the `alphaforge-api` script)
The arq pool is created at startup and used by handlers to enqueue jobs.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from alphaforge_api.routes import backtests, health, universes
from alphaforge_api.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.arq = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
    try:
        yield
    finally:
        await app.state.arq.close()


def create_app() -> FastAPI:
    app = FastAPI(title="AlphaForge API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().allowed_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(backtests.router)
    app.include_router(universes.router)
    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run("alphaforge_api.main:app", host="0.0.0.0", port=8000, reload=False)
