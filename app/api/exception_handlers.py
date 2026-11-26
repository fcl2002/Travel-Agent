"""Translate application errors into HTTP responses without leaking request secrets."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    AuthenticationError, AuthRateLimitError, InvalidCurrentPasswordError, PasswordUnchangedError,
    UserAlreadyExistsError, UserNotFoundError,
)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500, content={"detail": "Internal server error"},
            headers={"X-Request-ID": request.state.request_id, "Cache-Control": "no-store"},
        )

    @app.exception_handler(PasswordUnchangedError)
    async def password_unchanged(request: Request, exc: PasswordUnchangedError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"detail": "New password must be different from the current password"},
            headers={"Cache-Control": "no-store"},
        )

    @app.exception_handler(InvalidCurrentPasswordError)
    async def invalid_current_password(request: Request, exc: InvalidCurrentPasswordError) -> JSONResponse:
        return JSONResponse(
            status_code=403, content={"detail": "Current password is incorrect"},
            headers={"Cache-Control": "no-store"},
        )

    @app.exception_handler(AuthenticationError)
    async def invalid_credentials(request: Request, exc: AuthenticationError) -> JSONResponse:
        return JSONResponse(
            status_code=401, content={"detail": "Invalid credentials"},
            headers={"WWW-Authenticate": "Bearer", "Cache-Control": "no-store"},
        )

    @app.exception_handler(AuthRateLimitError)
    async def too_many_logins(request: Request, exc: AuthRateLimitError) -> JSONResponse:
        return JSONResponse(
            status_code=429, content={"detail": "Too many authentication attempts"},
            headers={"Retry-After": str(exc.retry_after), "Cache-Control": "no-store"},
        )

    @app.exception_handler(UserNotFoundError)
    async def user_not_found(request: Request, exc: UserNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "User not found"})

    @app.exception_handler(UserAlreadyExistsError)
    async def user_conflict(request: Request, exc: UserAlreadyExistsError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": "Username or email already exists"})

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {key: error[key] for key in ("loc", "msg", "type")}
            for error in exc.errors()
        ]
        return JSONResponse(status_code=422, content={"detail": errors})
