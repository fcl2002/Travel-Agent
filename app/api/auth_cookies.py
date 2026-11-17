"""HTTP-only refresh cookie handling; token contents stay out of JSON responses."""

from datetime import UTC, datetime

from fastapi import Response

from app.core.config import get_settings
from app.models.auth_session import AuthTokens

COOKIE_NAME = "refresh_token"
COOKIE_PATH = "/auth"


def set_refresh_cookie(response: Response, tokens: AuthTokens) -> None:
    response.set_cookie(
        COOKIE_NAME, tokens.refresh_token,
        max_age=max(0, int((tokens.refresh_expires_at - datetime.now(UTC)).total_seconds())),
        expires=tokens.refresh_expires_at, path=COOKIE_PATH,
        secure=get_settings().refresh_cookie_secure, httponly=True, samesite="strict",
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        COOKIE_NAME, path=COOKIE_PATH, secure=get_settings().refresh_cookie_secure,
        httponly=True, samesite="strict",
    )
    response.headers["Cache-Control"] = "no-store"
