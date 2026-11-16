"""HTTP entry point for the Travel Agent backend."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.endpoints.health import router as health_router
from app.api.endpoints.users import router as users_router
from app.api.exception_handlers import register_exception_handlers
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
    app.include_router(users_router)
    register_exception_handlers(app)
    return app


app = create_app()
