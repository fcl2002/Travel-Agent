"""Basic user management. Authentication will be added separately."""

from dataclasses import replace
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.dependencies import get_user_repository
from app.core.exceptions import UserNotFoundError
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.error import ErrorResponse
from app.schemas.user import UserCreate, UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])
Repository = Annotated[UserRepository, Depends(get_user_repository)]


@router.post(
    "", response_model=UserRead, status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse}}, summary="Create a user",
)
async def create_user(data: UserCreate, repository: Repository, response: Response) -> User:
    user = await repository.add(User.create(
        username=data.username, email=str(data.email),
        password_hash=data.password_hash.get_secret_value(),
    ))
    response.headers["Location"] = f"/users/{user.id}"
    return user


@router.get("", response_model=list[UserRead], summary="List users")
async def list_users(
    repository: Repository,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[User]:
    return await repository.list(limit=limit, offset=offset)


@router.get(
    "/{user_id}", response_model=UserRead,
    responses={404: {"model": ErrorResponse}}, summary="Get a user by ID",
)
async def read_user(user_id: UUID, repository: Repository) -> User:
    user = await repository.get_by_id(user_id)
    if user is None:
        raise UserNotFoundError("User not found")
    return user


@router.patch(
    "/{user_id}", response_model=UserRead,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
    summary="Update a user",
)
async def update_user(user_id: UUID, data: UserUpdate, repository: Repository) -> User:
    user = await read_user(user_id, repository)
    return await repository.update(replace(user, **data.model_dump(exclude_unset=True)))


@router.patch(
    "/{user_id}/deactivate", response_model=UserRead,
    responses={404: {"model": ErrorResponse}}, summary="Deactivate a user",
    description="Mark the user as inactive while preserving the stored record.",
)
async def deactivate_user(user_id: UUID, repository: Repository) -> User:
    return await repository.deactivate(user_id)
