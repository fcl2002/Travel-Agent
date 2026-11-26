"""Run migrations and writes in a temporary PostgreSQL schema, rolled back after each test."""

import asyncio
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.schema import CreateSchema

from app.core.config import get_settings
from app.db.session import transaction
from app.repositories.sqlalchemy.user_repository import SQLAlchemyUserRepository


@pytest.fixture
def anyio_backend():
    return "asyncio", {"loop_factory": asyncio.SelectorEventLoop}


@pytest.fixture(scope="session")
def database_url():
    url = get_settings().database_url
    if make_url(url).get_backend_name() != "postgresql":
        pytest.fail("Integration tests require a PostgreSQL DATABASE_URL.")
    return url


@pytest.fixture
async def migrated_database(database_url):
    engine = create_async_engine(database_url, connect_args={"connect_timeout": 3})
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))

    def upgrade(connection):
        config.attributes["connection"] = connection
        command.upgrade(config, "head")

    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                schema = f"test_{uuid4().hex}"
                await connection.execute(CreateSchema(schema))
                await connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                await connection.run_sync(upgrade)
                yield connection, config
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()


@pytest.fixture
async def repository_session(migrated_database):
    connection, _ = migrated_database
    async with AsyncSession(
        bind=connection, expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    ) as session:
        yield session


@pytest.fixture
async def user_repository(repository_session):
    async with transaction(repository_session):
        yield SQLAlchemyUserRepository(repository_session)
