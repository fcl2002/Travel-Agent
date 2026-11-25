"""SQLAlchemy adapter. Writes flush; the caller owns the transaction boundary."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.core.exceptions import UserAlreadyExistsError, UserNotFoundError
from app.repositories.user_repository import UserRepository
from app.db.tables.user import UserModel

UNIQUE_VIOLATION = "23505"  # PostgreSQL SQLSTATE


class SQLAlchemyUserRepository(UserRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _to_entity(model: UserModel) -> User:
        return User(
            id=model.id, username=model.username, email=model.email,
            _password_hash=model.password_hash, created_at=model.created_at.astimezone(UTC),
            update_at=model.update_at.astimezone(UTC) if model.update_at is not None else None,
            is_active=model.is_active,
        )

    async def _flush(self) -> None:
        try:
            await self.session.flush()
        except IntegrityError as exc:
            if getattr(exc.orig, "sqlstate", None) == UNIQUE_VIOLATION:
                raise UserAlreadyExistsError(
                    "A user with this id, username, or email already exists."
                ) from None
            raise

    async def add(self, user: User) -> User:
        model = UserModel(
            id=user.id, username=user.username, email=user.email,
            password_hash=user.password_hash, created_at=user.created_at,
            update_at=user.update_at,
            is_active=user.is_active,
        )
        self.session.add(model)
        await self._flush()
        return self._to_entity(model)

    async def get_by_id(self, user_id: UUID) -> User | None:
        model = await self.session.get(UserModel, user_id)
        return self._to_entity(model) if model is not None else None

    async def get_by_username(self, username: str) -> User | None:
        model = await self.session.scalar(select(UserModel).where(UserModel.username == username))
        return self._to_entity(model) if model is not None else None

    async def get_by_email(self, email: str) -> User | None:
        model = await self.session.scalar(select(UserModel).where(UserModel.email == email))
        return self._to_entity(model) if model is not None else None

    async def list(self, *, limit: int = 100, offset: int = 0) -> list[User]:
        if limit < 1 or offset < 0:
            raise ValueError("Limit must be positive and offset must be non-negative.")
        statement = select(UserModel).order_by(UserModel.created_at, UserModel.id)
        models = await self.session.scalars(statement.limit(limit).offset(offset))
        return [self._to_entity(model) for model in models]

    async def update(self, user: User) -> User:
        model = await self.session.get(UserModel, user.id)
        if model is None:
            raise UserNotFoundError("User not found.")
        model.username = user.username
        model.email = user.email
        model.password_hash = user.password_hash
        model.is_active = user.is_active
        model.update_at = datetime.now(UTC)
        await self._flush()
        return self._to_entity(model)

    async def deactivate(self, user_id: UUID) -> User:
        model = await self.session.get(UserModel, user_id)
        if model is None:
            raise UserNotFoundError("User not found.")
        model.is_active = False
        model.update_at = datetime.now(UTC)
        await self._flush()
        return self._to_entity(model)
