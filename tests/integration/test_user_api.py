from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password
from app.db.session import get_session, transaction
from app.main import create_app
from app.repositories.sqlalchemy.user_repository import SQLAlchemyUserRepository

pytestmark = [pytest.mark.integration, pytest.mark.anyio]
PAYLOAD = {"username": "traveler", "email": "traveler@example.com", "password": "A user supplied password!"}


@pytest.fixture
async def client(repository_session):
    app = create_app()

    async def session_dependency():
        async with transaction(repository_session):
            yield repository_session

    app.dependency_overrides[get_session] = session_dependency
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
        yield client


async def test_user_routes_lifecycle(client, repository_session):
    response = await client.post("/users", json=PAYLOAD)
    assert response.status_code == 201
    user = response.json()
    assert set(user) == {"id", "username", "email", "created_at", "update_at", "is_active"}
    assert user["is_active"] is True and user["update_at"] is None
    async with AsyncSession(bind=repository_session.bind, join_transaction_mode="create_savepoint") as session:
        stored = await SQLAlchemyUserRepository(session).get_by_id(UUID(user["id"]))
    assert stored.password_hash.startswith("$argon2id$")
    assert stored.password_hash != PAYLOAD["password"]
    assert verify_password(PAYLOAD["password"], stored.password_hash) is True
    location = response.headers["Location"]
    assert location == f"/users/{user['id']}"
    assert (await client.get(location)).json() == user
    assert (await client.get("/users", params={"limit": 1, "offset": 0})).json() == [user]

    response = await client.patch(location, json={"username": "updated"})
    assert response.status_code == 200
    updated = response.json()
    assert updated["username"] == "updated" and updated["email"] == user["email"]
    assert updated["created_at"] == user["created_at"] and updated["update_at"] is not None
    response = await client.patch(f"{location}/deactivate")
    assert response.status_code == 200 and response.json()["is_active"] is False
    assert (await client.delete(location)).status_code == 405
    assert (await client.get(location)).json() == response.json()


async def test_user_routes_errors_and_validation(client):
    original = (await client.post("/users", json=PAYLOAD)).json()
    other = {**PAYLOAD, "username": "another", "email": "another@example.com"}
    assert (await client.post("/users", json=other)).status_code == 201
    for duplicate in ({**other, "username": PAYLOAD["username"]}, {**other, "email": PAYLOAD["email"]}):
        response = await client.post("/users", json=duplicate)
        assert response.status_code == 409
        assert response.json() == {"detail": "Username or email already exists"}
    location = f"/users/{original['id']}"
    response = await client.patch(location, json={"username": "another", "email": "changed@example.com"})
    assert response.status_code == 409
    assert (await client.get(location)).json() == original

    missing = f"/users/{uuid4()}"
    for method, path, body in (("GET", missing, None), ("PATCH", missing, {"username": "missing"}),
                               ("PATCH", f"{missing}/deactivate", None)):
        response = await client.request(method, path, json=body)
        assert response.status_code == 404 and response.json() == {"detail": "User not found"}
    for body in ({**PAYLOAD, "email": "invalid"}, {**PAYLOAD, "password": " "},
                 {**PAYLOAD, "username": " "}, {**PAYLOAD, "is_active": False},
                 {**PAYLOAD, "password_hash": "client-supplied-hash"}):
        response = await client.post("/users", json=body)
        assert response.status_code == 422
        assert PAYLOAD["password"] not in response.text
    for body in ({}, {"email": None}, {"password_hash": "private-hash"}):
        response = await client.patch(location, json=body)
        assert response.status_code == 422 and "private-hash" not in response.text
    assert (await client.get("/users/not-a-uuid")).status_code == 422
    assert (await client.get("/users", params={"limit": 101})).status_code == 422
