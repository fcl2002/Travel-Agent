"""Translate application errors into HTTP responses without leaking request secrets."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.exceptions import UserAlreadyExistsError, UserNotFoundError


def register_exception_handlers(app: FastAPI) -> None:
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
