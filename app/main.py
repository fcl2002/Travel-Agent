"""HTTP entry point for the Travel Agent backend."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.endpoints.health import router as health_router
from app.db.session import get_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        yield
    finally:
        if get_engine.cache_info().currsize:
            await get_engine().dispose()
            get_engine.cache_clear()


def create_app() -> FastAPI:
    app = FastAPI(title="Travel Agent API", version="0.1.0", lifespan=lifespan)
    app.include_router(health_router)
    return app


app = create_app()
