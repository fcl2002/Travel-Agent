from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

from app.api.dependencies import check_auth_rate_limit, check_csrf, get_auth_service
from app.api.auth_cookies import COOKIE_NAME, clear_refresh_cookie, set_refresh_cookie
from app.core.exceptions import AuthenticationError
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.error import ErrorResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])
Service = Annotated[AuthService, Depends(get_auth_service)]


@router.post(
    "/login", response_model=TokenResponse, dependencies=[Depends(check_auth_rate_limit)],
    responses={401: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
    summary="Authenticate with email and password",
    description="Valid credentials reactivate an inactive account and create a new login session.",
)
async def login(
    data: LoginRequest, service: Service, response: Response,
) -> TokenResponse:
    tokens = await service.login(email=str(data.email), password=data.password.get_secret_value())
    set_refresh_cookie(response, tokens)
    return TokenResponse(access_token=tokens.access_token)


@router.post(
    "/refresh", response_model=TokenResponse, dependencies=[Depends(check_csrf)],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
    summary="Rotate the refresh cookie and issue a new access token",
)
async def refresh(request: Request, response: Response, service: Service) -> TokenResponse | JSONResponse:
    token = request.cookies.get(COOKIE_NAME)
    try:
        tokens = await service.refresh(token) if token else None
    except AuthenticationError:
        tokens = None
    if tokens is None:
        # Returning a response commits replay revocation instead of rolling it back.
        failure = JSONResponse(status_code=401, content={"detail": "Invalid credentials"},
                               headers={"WWW-Authenticate": "Bearer"})
        clear_refresh_cookie(failure)
        return failure
    set_refresh_cookie(response, tokens)
    return TokenResponse(access_token=tokens.access_token)


@router.post(
    "/logout", status_code=204, dependencies=[Depends(check_csrf)],
    responses={403: {"model": ErrorResponse}}, summary="Revoke this login session and clear its cookie",
)
async def logout(request: Request, service: Service) -> Response:
    await service.logout(request.cookies.get(COOKIE_NAME))
    response = Response(status_code=204)
    clear_refresh_cookie(response)
    return response
