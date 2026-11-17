from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError
from app.db.tables.auth_session import AuthSessionModel
from app.models.auth_session import AuthSession
from app.repositories.auth_session_repository import AuthSessionRepository


class SQLAlchemyAuthSessionRepository(AuthSessionRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, session: AuthSession) -> None:
        self.session.add(AuthSessionModel(
            id=session.id, user_id=session.user_id, refresh_token_hash=session.refresh_token_hash,
            created_at=session.created_at, expires_at=session.expires_at, revoked_at=session.revoked_at,
        ))
        await self.session.flush()

    async def get_by_id(self, session_id: UUID, *, for_update: bool = False) -> AuthSession | None:
        statement = select(AuthSessionModel).where(AuthSessionModel.id == session_id)
        if for_update:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        model = await self.session.scalar(statement)
        if model is None:
            return None
        return AuthSession(
            id=model.id, user_id=model.user_id, refresh_token_hash=model.refresh_token_hash,
            created_at=model.created_at.astimezone(UTC), expires_at=model.expires_at.astimezone(UTC),
            revoked_at=model.revoked_at.astimezone(UTC) if model.revoked_at else None,
        )

    async def save(self, session: AuthSession) -> None:
        model = await self.session.get(AuthSessionModel, session.id)
        if model is None:
            raise AuthenticationError()
        model.refresh_token_hash = session.refresh_token_hash
        model.revoked_at = session.revoked_at
        await self.session.flush()

    async def revoke_for_user(self, user_id: UUID) -> None:
        await self.session.execute(
            update(AuthSessionModel)
            .where(AuthSessionModel.user_id == user_id, AuthSessionModel.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
