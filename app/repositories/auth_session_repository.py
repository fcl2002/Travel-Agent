from abc import ABC, abstractmethod
from uuid import UUID

from app.models.auth_session import AuthSession


class AuthSessionRepository(ABC):
    @abstractmethod
    async def add(self, auth_session: AuthSession) -> None: ...

    @abstractmethod
    async def get_by_id(self, session_id: UUID, *, for_update: bool = False) -> AuthSession | None: ...

    @abstractmethod
    async def save(self, auth_session: AuthSession) -> None: ...

    @abstractmethod
    async def revoke_for_user(self, user_id: UUID) -> None: ...
