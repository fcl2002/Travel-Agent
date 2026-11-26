"""SQLAlchemy metadata shared by table mappings and Alembic."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
