"""Coordinate user operations through the repository contract."""

import asyncio
from dataclasses import replace
from uuid import UUID

from app.core.exceptions import PasswordUnchangedError, UserNotFoundError
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.repositories.user_repository import UserRepository


class UserService:
    def __init__(self, repository: UserRepository):
        self.repository = repository

    async def create(self, *, username: str, email: str, password: str) -> User:
        password_hash = await asyncio.to_thread(hash_password, password)
        return await self.repository.add(User.create(
            username=username, email=email, password_hash=password_hash,
        ))

    async def get(self, user_id: UUID) -> User:
        user = await self.repository.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError("User not found")
        return user

    async def list(self, *, limit: int = 100, offset: int = 0) -> list[User]:
        return await self.repository.list(limit=limit, offset=offset)

    async def update(
        self, user_id: UUID, *, username: str | None = None, email: str | None = None,
        password: str | None = None,
    ) -> User:
        user = await self.get(user_id)
        changes = {
            name: value for name, value in (("username", username), ("email", email))
            if value is not None
        }
        if password is not None:
            if await asyncio.to_thread(verify_password, password, user.password_hash):
                raise PasswordUnchangedError()
            changes["password_hash"] = await asyncio.to_thread(hash_password, password)
        return await self.repository.update(replace(user, **changes))

    async def deactivate(self, user_id: UUID) -> User:
        return await self.repository.deactivate(user_id)
