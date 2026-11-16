"""Persistence contract expressed using domain objects."""

from abc import ABC, abstractmethod
from uuid import UUID

from app.models.user import User


class UserRepository(ABC):
    @abstractmethod
    async def add(self, user: User) -> User: ...

    @abstractmethod
    async def get_by_id(self, user_id: UUID) -> User | None: ...

    @abstractmethod
    async def get_by_username(self, username: str) -> User | None: ...

    @abstractmethod
    async def get_by_email(self, email: str) -> User | None: ...

    @abstractmethod
    async def list(self, *, limit: int = 100, offset: int = 0) -> list[User]: ...

    @abstractmethod
    async def update(self, user: User) -> User: ...

    @abstractmethod
    async def deactivate(self, user_id: UUID) -> User: ...
