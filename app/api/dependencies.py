"""Dependency wiring: connect HTTP dependencies to infrastructure adapters here."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.probe import SQLAlchemyDatabaseProbe
from app.db.session import get_session
from app.repositories.database_probe import DatabaseProbe
from app.repositories.sqlalchemy.user_repository import SQLAlchemyUserRepository
from app.repositories.user_repository import UserRepository


async def get_database_probe(
    session: Annotated[AsyncSession, Depends(get_session, scope="function")],
) -> DatabaseProbe:
    return SQLAlchemyDatabaseProbe(session)


async def get_user_repository(
    session: Annotated[AsyncSession, Depends(get_session, scope="function")],
) -> UserRepository:
    return SQLAlchemyUserRepository(session)
