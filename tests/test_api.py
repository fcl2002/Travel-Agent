import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from src.api import app
from src.database import get_engine


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_liveness_does_not_require_database(client):
    def unexpected_database_access():
        pytest.fail("Liveness must not access the database")

    app.dependency_overrides[get_engine] = unexpected_database_access
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_database_health_checks_connection(client):
    engine = create_engine("sqlite://")
    app.dependency_overrides[get_engine] = lambda: engine
    try:
        response = client.get("/health/db")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
    finally:
        engine.dispose()


def test_database_failure_returns_503_without_connection_details(client, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'missing' / 'database.sqlite'}")
    app.dependency_overrides[get_engine] = lambda: engine
    try:
        response = client.get("/health/db")
        assert response.status_code == 503
        assert response.json() == {"detail": "Database unavailable"}
    finally:
        engine.dispose()
