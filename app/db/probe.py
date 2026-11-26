import logging

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class SQLAlchemyDatabaseProbe:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def is_available(self) -> bool:
        try:
            await self.session.execute(text("SELECT 1"))
        except SQLAlchemyError as exc:
            logger.error("database_unavailable", extra={"error_type": type(exc).__name__})
            return False
        return True
