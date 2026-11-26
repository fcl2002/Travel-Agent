"""Coordinate user operations through the repository contract."""

import asyncio
from dataclasses import replace
from uuid import UUID

from app.core.exceptions import InvalidCurrentPasswordError, PasswordUnchangedError, UserNotFoundError
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.repositories.auth_session_repository import AuthSessionRepository
from app.repositories.user_repository import UserRepository


class UserService:
    def __init__(self, repository: UserRepository, sessions: AuthSessionRepository):
        self.repository = repository
        self.sessions = sessions

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
        password: str | None = None, current_password: str | None = None,
    ) -> User:
        user = await self.get(user_id)
        if email is not None or password is not None:
            # Re-authenticate: a stolen access token alone must not take over the account.
            if current_password is None or not await asyncio.to_thread(
                verify_password, current_password, user.password_hash,
            ):
                raise InvalidCurrentPasswordError()
        changes = {
            name: value for name, value in (("username", username), ("email", email))
            if value is not None
        }
        if password is not None:
            # current_password was just verified, so equal strings mean the same password.
            if password == current_password:
                raise PasswordUnchangedError()
            changes["password_hash"] = await asyncio.to_thread(hash_password, password)
        updated = await self.repository.update(replace(user, **changes))
        if password is not None:
            # Sessions opened with the old password, possibly by an attacker, must not survive it.
            await self.sessions.revoke_for_user(user_id)
        return updated

    async def deactivate(self, user_id: UUID) -> User:
        return await self.repository.deactivate(user_id)
