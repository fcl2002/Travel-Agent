"""Public registration and authenticated access to the caller's own account."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.dependencies import check_auth_rate_limit, get_current_user, get_user_service
from app.models.user import User
from app.schemas.error import ErrorResponse
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.services.user_service import UserService

# Account routes use /me, never a user ID: there is no ID to guess and no ownership check to forget.
# A future admin /{user_id} route must be declared after /me, or "me" is parsed as a UUID.
router = APIRouter(prefix="/users", tags=["users"])
Service = Annotated[UserService, Depends(get_user_service)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post(
    "", response_model=UserRead, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(check_auth_rate_limit)],
    responses={409: {"model": ErrorResponse}, 429: {"model": ErrorResponse}}, summary="Create a user",
)
async def create_user(data: UserCreate, service: Service, response: Response) -> User:
    user = await service.create(
        username=data.username, email=str(data.email),
        password=data.password.get_secret_value(),
    )
    response.headers["Cache-Control"] = "no-store"
    return user


@router.get(
    "/me", response_model=UserRead, responses={401: {"model": ErrorResponse}},
    summary="Get the authenticated account",
)
async def read_current_user(current_user: CurrentUser) -> User:
    return current_user


@router.patch(
    "/me", response_model=UserRead,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
    summary="Update the authenticated account",
)
async def update_current_user(data: UserUpdate, current_user: CurrentUser, service: Service) -> User:
    changes = data.model_dump(exclude_unset=True)
    if data.password is not None:
        changes["password"] = data.password.get_secret_value()
    return await service.update(current_user.id, **changes)


@router.patch(
    "/me/deactivate", response_model=UserRead,
    responses={401: {"model": ErrorResponse}},
    summary="Deactivate the authenticated account",
    description=(
        "Mark the user as inactive while preserving the stored record. "
        "Logging in again with valid credentials reactivates the account."
    ),
)
async def deactivate_current_user(current_user: CurrentUser, service: Service) -> User:
    return await service.deactivate(current_user.id)
