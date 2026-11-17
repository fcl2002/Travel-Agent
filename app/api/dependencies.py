"""Dependency wiring: connect HTTP dependencies to infrastructure adapters here."""

from functools import lru_cache
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, Response, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.probe import SQLAlchemyDatabaseProbe
from app.db.session import get_session
from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, UserNotFoundError
from app.core.rate_limit import AuthRateLimiter
from app.core.tokens import JWTTokenService
from app.models.user import User
from app.repositories.database_probe import DatabaseProbe
from app.repositories.sqlalchemy.user_repository import SQLAlchemyUserRepository
from app.repositories.user_repository import UserRepository
from app.repositories.auth_session_repository import AuthSessionRepository
from app.repositories.sqlalchemy.auth_session_repository import SQLAlchemyAuthSessionRepository
from app.services.user_service import UserService
from app.services.auth_service import AuthService

bearer = HTTPBearer(auto_error=False)


@lru_cache
def get_token_service() -> JWTTokenService:
    settings = get_settings()
    if settings.jwt_secret_key is None:
        raise RuntimeError("Set JWT_SECRET_KEY to a cryptographically random secret before starting the API")
    return JWTTokenService(
        secret=settings.jwt_secret_key.get_secret_value(),
        expires_minutes=settings.access_token_expire_minutes,
        issuer=settings.jwt_issuer, audience=settings.jwt_audience,
    )


@lru_cache
def get_auth_limiter() -> AuthRateLimiter:
    return AuthRateLimiter()


async def check_auth_rate_limit(
    request: Request, limiter: Annotated[AuthRateLimiter, Depends(get_auth_limiter)],
) -> None:
    limiter.check(request.client.host if request.client else "unknown")


async def get_database_probe(
    session: Annotated[AsyncSession, Depends(get_session, scope="function")],
) -> DatabaseProbe:
    return SQLAlchemyDatabaseProbe(session)


async def get_user_repository(
    session: Annotated[AsyncSession, Depends(get_session, scope="function")],
) -> UserRepository:
    return SQLAlchemyUserRepository(session)


async def get_user_service(
    repository: Annotated[UserRepository, Depends(get_user_repository)],
) -> UserService:
    return UserService(repository)


async def get_auth_session_repository(
    session: Annotated[AsyncSession, Depends(get_session, scope="function")],
) -> AuthSessionRepository:
    return SQLAlchemyAuthSessionRepository(session)


async def get_auth_service(
    repository: Annotated[UserRepository, Depends(get_user_repository)],
    sessions: Annotated[AuthSessionRepository, Depends(get_auth_session_repository)],
    tokens: Annotated[JWTTokenService, Depends(get_token_service)],
) -> AuthService:
    return AuthService(repository, sessions, tokens, refresh_days=get_settings().refresh_token_expire_days)


async def check_cookie_request(
    request: Request,
    requested_with: Annotated[str | None, Header(alias="X-Requested-With")] = None,
) -> None:
    allowed = {str(request.base_url).rstrip("/")}
    frontend = get_settings().frontend_origin
    if frontend:
        allowed.add(frontend.rstrip("/"))
    origin = request.headers.get("origin")
    if requested_with != "XMLHttpRequest" or (origin is not None and origin not in allowed):
        raise HTTPException(status_code=403, detail="Invalid refresh/logout request origin")


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer)],
    service: Annotated[AuthService, Depends(get_auth_service)],
    response: Response,
) -> User:
    if credentials is None:
        raise AuthenticationError()
    user = await service.get_current_user(credentials.credentials)
    response.headers["Cache-Control"] = "no-store"
    return user


async def get_owned_user(
    user_id: UUID, current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if current_user.id != user_id:
        raise UserNotFoundError("User not found")
    return current_user
