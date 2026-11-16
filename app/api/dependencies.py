"""Dependency wiring: connect HTTP dependencies to infrastructure adapters here."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.probe import SQLAlchemyDatabaseProbe
from app.db.session import get_session
from app.repositories.database_probe import DatabaseProbe


async def get_database_probe(
    session: Annotated[AsyncSession, Depends(get_session, scope="function")],
) -> DatabaseProbe:
    return SQLAlchemyDatabaseProbe(session)
