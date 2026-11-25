from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from alembic import command
import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UserAlreadyExistsError, UserNotFoundError
from app.db.session import transaction
from app.models.user import User
from app.repositories.sqlalchemy.user_repository import SQLAlchemyUserRepository

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


def new_user(username="traveler", email="traveler@example.com"):
    return User.create(username=username, email=email, password_hash="already-hashed-password")


async def test_user_lifecycle(repository_session):
    user_repository = SQLAlchemyUserRepository(repository_session)
    async with transaction(repository_session):
        user = await user_repository.add(new_user())
        assert user.is_active and user.created_at.utcoffset().total_seconds() == 0
        assert user.updated_at is None
        assert user.password_hash == "already-hashed-password"
        assert user.password_hash not in repr(user)
        assert await user_repository.get_by_username(user.username) == user
        assert await user_repository.get_by_email(user.email) == user

        before_update = datetime.now(UTC)
        updated = await user_repository.update(replace(
            user, username="updated", email="updated@example.com", password_hash="new-hash",
            created_at=datetime(2000, 1, 1, tzinfo=UTC), updated_at=datetime(2000, 1, 1, tzinfo=UTC),
        ))
        assert before_update <= updated.updated_at <= datetime.now(UTC)
        assert updated.updated_at.utcoffset().total_seconds() == 0
        assert updated == replace(user, username="updated", email="updated@example.com",
                                  password_hash="new-hash", updated_at=updated.updated_at)
        assert await user_repository.get_by_id(user.id) == updated
        another = await user_repository.add(new_user("another", "another@example.com"))
        assert await user_repository.list(limit=1, offset=1) == [another]
        before_deactivation = datetime.now(UTC)
        inactive = await user_repository.deactivate(user.id)
        assert before_deactivation <= inactive.updated_at <= datetime.now(UTC)
        assert inactive == replace(updated, is_active=False, updated_at=inactive.updated_at)
        assert await user_repository.get_by_id(user.id) == inactive
        assert await user_repository.list() == [inactive, another]
    async with AsyncSession(bind=repository_session.bind, join_transaction_mode="create_savepoint") as session:
        assert await SQLAlchemyUserRepository(session).list() == [inactive, another]


@pytest.mark.parametrize("failure", ["username", "email", "missing_user"])
async def test_failed_sequence_rolls_back_all_writes(repository_session, failure):
    repository = SQLAlchemyUserRepository(repository_session)
    async with transaction(repository_session):
        original = await repository.add(new_user())
    error = UserNotFoundError if failure == "missing_user" else UserAlreadyExistsError
    with pytest.raises(error):
        async with transaction(repository_session):
            await repository.deactivate(original.id)
            await repository.add(new_user("pending", "pending@example.com"))
            candidate = new_user("another", "another@example.com")
            if failure == "missing_user":
                await repository.update(candidate)
            else:
                await repository.add(replace(candidate, **{failure: getattr(original, failure)}))
    async with AsyncSession(bind=repository_session.bind, join_transaction_mode="create_savepoint") as session:
        assert await SQLAlchemyUserRepository(session).list() == [original]


async def test_missing_user(user_repository):
    assert await user_repository.get_by_id(uuid4()) is None
    assert await user_repository.get_by_username("missing") is None
    assert await user_repository.get_by_email("missing@example.com") is None
    with pytest.raises(UserNotFoundError):
        await user_repository.deactivate(uuid4())


async def test_migration_matches_models_and_can_be_reverted(migrated_database):
    connection, config = migrated_database

    def verify(connection):
        command.check(config)
        command.downgrade(config, "0001_create_users")
        assert "updated_at" not in {column["name"] for column in inspect(connection).get_columns("users")}
        created_at = datetime(2020, 1, 1, tzinfo=UTC)
        connection.execute(text(
            "INSERT INTO users (id, username, email, password_hash, created_at) "
            "VALUES (:id, 'legacy', 'legacy@example.com', 'hash', :created_at)"
        ), {"id": uuid4(), "created_at": created_at})
        command.upgrade(config, "head")
        row = connection.execute(text("SELECT created_at, updated_at FROM users")).one()
        assert row.created_at == created_at and row.updated_at is None
        command.downgrade(config, "base")
        assert "users" not in inspect(connection).get_table_names()

    await connection.run_sync(verify)
