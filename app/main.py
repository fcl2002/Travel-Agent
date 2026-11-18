"""HTTP entry point for the Travel Agent backend."""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.endpoints.health import router as health_router
from app.api.endpoints.auth import router as auth_router
from app.api.dependencies import get_token_service
from app.api.endpoints.users import router as users_router
from app.api.exception_handlers import register_exception_handlers
from app.api.middleware import RequestLoggingMiddleware
from app.db.session import get_engine
from app.core.config import get_settings
from app.core.logging import configure_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_token_service()
    logger.info("application_started")
    try:
        yield
    finally:
        if get_engine.cache_info().currsize:
            await get_engine().dispose()
            get_engine.cache_clear()
        logger.info("application_stopped")


def create_app() -> FastAPI:
    configure_logging(get_settings().log_level)
    app = FastAPI(title="Travel Agent API", version="0.1.0", lifespan=lifespan)
    frontend = get_settings().frontend_origin
    if frontend:
        app.add_middleware(
            CORSMiddleware, allow_origins=[frontend.rstrip("/")], allow_credentials=True,
            allow_methods=["GET", "POST", "PATCH"],
            allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
            expose_headers=["X-Request-ID"],
        )
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(users_router)
    app.add_middleware(RequestLoggingMiddleware)
    register_exception_handlers(app)
    return app


app = create_app()
