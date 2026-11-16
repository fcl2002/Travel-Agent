from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_database_probe
from app.db.probe import SQLAlchemyDatabaseProbe
from app.main import create_app


@pytest.fixture
def client():
    with TestClient(create_app()) as client:
        yield client


def test_liveness_does_not_require_database(client):
    def unexpected_database_access():
        pytest.fail("Liveness must not access the database")

    client.app.dependency_overrides[get_database_probe] = unexpected_database_access
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_database_failure_returns_503_without_connection_details(client):
    session = AsyncMock(spec=AsyncSession)
    session.execute.side_effect = SQLAlchemyError("Private connection details")
    client.app.dependency_overrides[get_database_probe] = lambda: SQLAlchemyDatabaseProbe(session)
    response = client.get("/health/db")
    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
