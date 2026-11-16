"""Basic user management. Authentication will be added separately."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.dependencies import get_user_service
from app.models.user import User
from app.schemas.error import ErrorResponse
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])
Service = Annotated[UserService, Depends(get_user_service)]


@router.post(
    "", response_model=UserRead, status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse}}, summary="Create a user",
)
async def create_user(data: UserCreate, service: Service, response: Response) -> User:
    user = await service.create(
        username=data.username, email=str(data.email),
        password=data.password.get_secret_value(),
    )
    response.headers["Location"] = f"/users/{user.id}"
    return user


@router.get("", response_model=list[UserRead], summary="List users")
async def list_users(
    service: Service,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[User]:
    return await service.list(limit=limit, offset=offset)


@router.get(
    "/{user_id}", response_model=UserRead,
    responses={404: {"model": ErrorResponse}}, summary="Get a user by ID",
)
async def read_user(user_id: UUID, service: Service) -> User:
    return await service.get(user_id)


@router.patch(
    "/{user_id}", response_model=UserRead,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
    summary="Update a user",
)
async def update_user(user_id: UUID, data: UserUpdate, service: Service) -> User:
    return await service.update(user_id, **data.model_dump(exclude_unset=True))


@router.patch(
    "/{user_id}/deactivate", response_model=UserRead,
    responses={404: {"model": ErrorResponse}}, summary="Deactivate a user",
    description="Mark the user as inactive while preserving the stored record.",
)
async def deactivate_user(user_id: UUID, service: Service) -> User:
    return await service.deactivate(user_id)
