from uuid import UUID, uuid4

import httpx
import pytest
from datetime import UTC, datetime, timedelta
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password
from app.core.rate_limit import AuthRateLimiter
from app.api.dependencies import get_auth_limiter, get_token_service
from app.db.session import get_session, transaction
from app.main import create_app
from app.repositories.sqlalchemy.user_repository import SQLAlchemyUserRepository
from app.api.auth_cookies import COOKIE_NAME
from app.db.tables.auth_session import AuthSessionModel
from app.repositories.sqlalchemy.auth_session_repository import SQLAlchemyAuthSessionRepository
from app.services.auth_service import token_hash

pytestmark = [pytest.mark.integration, pytest.mark.anyio]
PAYLOAD = {"username": "traveler", "email": "traveler@example.com", "password": "A user supplied password1!"}


@pytest.fixture
def auth_limiter():
    return AuthRateLimiter()


@pytest.fixture
def application(repository_session, auth_limiter):
    app = create_app()

    async def session_dependency():
        async with transaction(repository_session):
            yield repository_session

    app.dependency_overrides[get_session] = session_dependency
    app.dependency_overrides[get_auth_limiter] = lambda: auth_limiter
    return app


@pytest.fixture
async def client(application):
    app = application
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="https://test") as client:
        yield client


async def test_user_routes_lifecycle(client, repository_session):
    response = await client.post("/users", json=PAYLOAD)
    assert response.status_code == 201
    user = response.json()
    assert set(user) == {"id", "username", "email", "created_at", "updated_at", "is_active"}
    assert user["is_active"] is True and user["updated_at"] is None
    async with AsyncSession(bind=repository_session.bind, join_transaction_mode="create_savepoint") as session:
        stored = await SQLAlchemyUserRepository(session).get_by_id(UUID(user["id"]))
    assert stored.password_hash.startswith("$argon2id$")
    assert verify_password(PAYLOAD["password"], stored.password_hash) is True
    location = response.headers["Location"]
    assert location == f"/users/{user['id']}"
    assert (await client.get(location)).status_code == 401
    login = await client.post("/auth/login", json={"email": PAYLOAD["email"], "password": PAYLOAD["password"]})
    assert login.status_code == 200 and login.headers["Cache-Control"] == "no-store"
    original_cookie = client.cookies.get(COOKIE_NAME)
    client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
    assert (await client.get("/users/me")).json() == user
    assert (await client.get(location)).json() == user
    assert (await client.get("/users")).status_code == 405

    response = await client.patch(location, json={"username": "updated"})
    assert response.status_code == 200
    updated = response.json()
    assert updated["username"] == "updated" and updated["email"] == user["email"]
    assert updated["created_at"] == user["created_at"] and updated["updated_at"] is not None
    # A second session lets us exercise inactive refresh without revoking the first.
    assert (await client.post("/auth/login", json={"email": PAYLOAD["email"], "password": PAYLOAD["password"]})).status_code == 200
    response = await client.patch(f"{location}/deactivate")
    assert response.status_code == 200 and response.json()["is_active"] is False
    inactive = response.json()
    assert (await client.delete(location)).status_code == 405
    assert (await client.get(location)).status_code == 401
    assert (await client.post("/auth/login", json={"email": PAYLOAD["email"], "password": "wrong-password"})).status_code == 401
    response = await client.post("/auth/refresh", headers={"X-Requested-With": "XMLHttpRequest", "Origin": "https://test"})
    assert response.status_code == 401 and client.cookies.get(COOKIE_NAME) is None
    async with transaction(repository_session):
        assert (await SQLAlchemyUserRepository(repository_session).get_by_id(UUID(user["id"]))).is_active is False

    reactivated_login = await client.post("/auth/login", json={"email": PAYLOAD["email"], "password": PAYLOAD["password"]})
    assert reactivated_login.status_code == 200
    reactivated_cookie = client.cookies.get(COOKIE_NAME)
    # Reactivation does not revive the first session's access or refresh tokens.
    assert (await client.get(location)).status_code == 401
    response = await client.post("/auth/refresh", headers={**COOKIE_HEADERS, "Cookie": f"{COOKIE_NAME}={original_cookie}"})
    assert response.status_code == 401
    client.headers["Authorization"] = f"Bearer {reactivated_login.json()['access_token']}"
    reactivated = (await client.get(location)).json()
    assert reactivated == {**inactive, "is_active": True, "updated_at": reactivated["updated_at"]}
    assert datetime.fromisoformat(reactivated["updated_at"]) > datetime.fromisoformat(inactive["updated_at"])
    response = await client.post("/auth/refresh", headers={**COOKIE_HEADERS, "Cookie": f"{COOKIE_NAME}={reactivated_cookie}"})
    assert response.status_code == 200


async def test_user_routes_errors_and_validation(client):
    original = (await client.post("/users", json=PAYLOAD)).json()
    other = {**PAYLOAD, "username": "another", "email": "another@example.com"}
    assert (await client.post("/users", json=other)).status_code == 201
    response = await client.post("/users", json={**other, "username": PAYLOAD["username"]})
    assert response.status_code == 409
    assert response.json() == {"detail": "Username or email already exists"}
    login = await client.post("/auth/login", json={"email": PAYLOAD["email"], "password": PAYLOAD["password"]})
    client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
    location = f"/users/{original['id']}"
    response = await client.patch(location, json={"username": "another", "email": "changed@example.com"})
    assert response.status_code == 409
    assert (await client.get(location)).json() == original

    missing = f"/users/{uuid4()}"
    for method, path, body in (("GET", missing, None), ("PATCH", missing, {"username": "missing"}),
                               ("PATCH", f"{missing}/deactivate", None)):
        response = await client.request(method, path, json=body)
        assert response.status_code == 404 and response.json() == {"detail": "User not found"}
    for body in ({**PAYLOAD, "email": "invalid"}, {**PAYLOAD, "password": "short"},
                 {**PAYLOAD, "password": " "},
                 {**PAYLOAD, "username": " "}, {**PAYLOAD, "is_active": False},
                 {**PAYLOAD, "password_hash": "client-supplied-hash"}):
        response = await client.post("/users", json=body)
        assert response.status_code == 422
        assert PAYLOAD["password"] not in response.text
    for body in ({}, {"email": None}, {"password_hash": "private-hash"}):
        response = await client.patch(location, json=body)
        assert response.status_code == 422 and "private-hash" not in response.text
    assert (await client.get("/users/not-a-uuid")).status_code == 422


async def test_auth_rejects_bad_credentials_tokens_and_foreign_accounts(client):
    own = (await client.post("/users", json=PAYLOAD)).json()
    other = (await client.post("/users", json={**PAYLOAD, "username": "another", "email": "another@example.com"})).json()
    for email, password in ((PAYLOAD["email"], "wrong password"), ("missing@example.com", PAYLOAD["password"])):
        response = await client.post("/auth/login", json={"email": email, "password": password})
        assert response.status_code == 401 and response.json() == {"detail": "Invalid credentials"}
        assert response.headers["WWW-Authenticate"] == "Bearer"
    login = await client.post("/auth/login", json={"email": PAYLOAD["email"], "password": PAYLOAD["password"]})
    assert login.status_code == 200 and login.json()["token_type"] == "bearer"
    client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
    assert (await client.get("/users/me")).json() == own
    for method, path, body in (("GET", f"/users/{other['id']}", None),
                               ("PATCH", f"/users/{other['id']}", {"username": "hijacked"}),
                               ("PATCH", f"/users/{other['id']}", {"password": "Hijacked123!"}),
                               ("PATCH", f"/users/{other['id']}/deactivate", None)):
        response = await client.request(method, path, json=body)
        assert response.status_code == 404
    for token in ("invalid-token", get_token_service().create_access_token(uuid4(), uuid4())):
        response = await client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401
    other_login = await client.post("/auth/login", json={"email": "another@example.com", "password": PAYLOAD["password"]})
    response = await client.get("/users/me", headers={"Authorization": f"Bearer {other_login.json()['access_token']}"})
    assert response.json() == other


async def test_login_and_registration_are_rate_limited(client, auth_limiter):
    auth_limiter.limit = 2
    credentials = {"email": "missing@example.com", "password": "wrong-password"}
    for _ in range(2):
        assert (await client.post("/auth/login", json=credentials)).status_code == 401
    response = await client.post("/auth/login", json=credentials)
    assert response.status_code == 429 and int(response.headers["Retry-After"]) > 0
    assert (await client.post("/users", json=PAYLOAD)).status_code == 429


COOKIE_HEADERS = {"X-Requested-With": "XMLHttpRequest", "Origin": "https://test"}


async def register_and_login(client):
    assert (await client.post("/users", json=PAYLOAD)).status_code == 201
    response = await client.post("/auth/login", json={"email": PAYLOAD["email"], "password": PAYLOAD["password"]})
    assert response.status_code == 200
    return response


async def test_password_update_requires_authentication_and_hashes_password(client, repository_session):
    login = await register_and_login(client)
    authorization = {"Authorization": f"Bearer {login.json()['access_token']}"}
    user = (await client.get("/users/me", headers=authorization)).json()
    location = f"/users/{user['id']}"
    password = "  New password123!  "

    for headers in ({}, {"Authorization": "Bearer invalid-token"}):
        response = await client.patch(location, json={"password": password}, headers=headers)
        assert response.status_code == 401

    async with transaction(repository_session):
        original = await SQLAlchemyUserRepository(repository_session).get_by_id(UUID(user["id"]))
        assert verify_password(PAYLOAD["password"], original.password_hash)

    response = await client.patch(location, json={"password": password}, headers=authorization)
    assert response.status_code == 200
    updated = response.json()
    assert updated == {**user, "updated_at": updated["updated_at"]}
    assert updated["updated_at"] is not None
    assert "password" not in updated and "password_hash" not in updated
    assert password not in response.text

    async with transaction(repository_session):
        stored = await SQLAlchemyUserRepository(repository_session).get_by_id(UUID(user["id"]))
        assert stored.password_hash.startswith("$argon2id$")
        assert stored.password_hash != original.password_hash
        assert verify_password(password, stored.password_hash)
        assert not verify_password(PAYLOAD["password"], stored.password_hash)

    credentials = {"email": PAYLOAD["email"], "password": PAYLOAD["password"]}
    assert (await client.post("/auth/login", json=credentials)).status_code == 401
    assert (await client.post("/auth/login", json={**credentials, "password": password})).status_code == 200
    # Updating profile data must preserve the new password hash.
    assert (await client.patch(location, json={"username": "updated"}, headers=authorization)).status_code == 200
    async with transaction(repository_session):
        unchanged = await SQLAlchemyUserRepository(repository_session).get_by_id(UUID(user["id"]))
        assert unchanged.password_hash == stored.password_hash


@pytest.mark.parametrize("change_password_first", [False, True])
async def test_password_update_rejects_current_password(client, repository_session, change_password_first):
    login = await register_and_login(client)
    client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
    user = (await client.get("/users/me")).json()
    location = f"/users/{user['id']}"
    password = PAYLOAD["password"]
    if change_password_first:
        password = "New password123!"
        assert (await client.patch(location, json={"password": password})).status_code == 200

    async with transaction(repository_session):
        before = await SQLAlchemyUserRepository(repository_session).get_by_id(UUID(user["id"]))

    response = await client.patch(location, json={"username": "changed", "password": password})
    assert response.status_code == 400
    assert response.json() == {"detail": "New password must be different from the current password"}
    assert response.headers["Cache-Control"] == "no-store"
    assert password not in response.text and before.password_hash not in response.text
    async with transaction(repository_session):
        after = await SQLAlchemyUserRepository(repository_session).get_by_id(UUID(user["id"]))
        assert after == before
        assert verify_password(password, after.password_hash)


async def test_invalid_password_updates_leave_account_unchanged(client, repository_session):
    login = await register_and_login(client)
    client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
    user = (await client.get("/users/me")).json()
    for password in (None, "", "Abcde1!", "A1!" + "a" * 126, "abcdef1!", "Abcdefg!",
                     "Abcdef12", "Abcdef1 ", "Abcdef1\n", "        "):
        response = await client.patch(f"/users/{user['id']}", json={"username": "changed", "password": password})
        assert response.status_code == 422
        assert all("input" not in error for error in response.json()["detail"])
        if password and password.strip():
            assert password not in response.text
    assert (await client.get("/users/me")).json() == user
    async with transaction(repository_session):
        stored = await SQLAlchemyUserRepository(repository_session).get_by_id(UUID(user["id"]))
        assert verify_password(PAYLOAD["password"], stored.password_hash)


async def test_failed_reactivation_rolls_back_user_and_sessions(client, repository_session, monkeypatch):
    login = await register_and_login(client)
    identity = get_token_service().decode_refresh_token(client.cookies.get(COOKIE_NAME))
    client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
    inactive = (await client.patch(f"/users/{identity.user_id}/deactivate")).json()
    original_add = SQLAlchemyAuthSessionRepository.add
    failed_sessions = []

    async def fail_after_flush(self, session):
        await original_add(self, session)
        failed_sessions.append(session.id)
        raise RuntimeError("Simulated failure after creating the login session")

    with monkeypatch.context() as patch:
        patch.setattr(SQLAlchemyAuthSessionRepository, "add", fail_after_flush)
        with pytest.raises(RuntimeError):
            await client.post("/auth/login", json={"email": PAYLOAD["email"], "password": PAYLOAD["password"]})

    async with transaction(repository_session):
        user = await SQLAlchemyUserRepository(repository_session).get_by_id(identity.user_id)
        assert user.is_active is False
        assert user.updated_at == datetime.fromisoformat(inactive["updated_at"])
        sessions = SQLAlchemyAuthSessionRepository(repository_session)
        assert (await sessions.get_by_id(identity.session_id)).revoked_at is None
        assert await sessions.get_by_id(failed_sessions[0]) is None
    assert (await client.post("/auth/login", json={"email": PAYLOAD["email"], "password": PAYLOAD["password"]})).status_code == 200


async def test_refresh_rotation_and_logout(client, repository_session):
    login = await register_and_login(client)
    assert set(login.json()) == {"access_token", "token_type"}
    cookie_header = login.headers["Set-Cookie"]
    assert all(flag in cookie_header for flag in ("HttpOnly", "Secure", "SameSite=strict", "Path=/auth"))
    first_cookie = client.cookies.get(COOKIE_NAME)
    identity = get_token_service().decode_refresh_token(first_cookie)
    async with AsyncSession(bind=repository_session.bind, join_transaction_mode="create_savepoint") as session:
        stored = await SQLAlchemyAuthSessionRepository(session).get_by_id(identity.session_id)
    assert stored.refresh_token_hash == token_hash(first_cookie)
    assert first_cookie not in repr(stored)
    # No Authorization header: this simulates losing the access token on a page reload.
    refreshed = await client.post("/auth/refresh", headers=COOKIE_HEADERS)
    assert refreshed.status_code == 200
    current_cookie = client.cookies.get(COOKIE_NAME)
    assert current_cookie != first_cookie
    assert refreshed.json()["access_token"] != login.json()["access_token"]
    authorization = {"Authorization": f"Bearer {refreshed.json()['access_token']}"}
    assert (await client.get("/users/me", headers=authorization)).status_code == 200
    logout = await client.post("/auth/logout", headers=COOKIE_HEADERS)
    assert logout.status_code == 204 and client.cookies.get(COOKIE_NAME) is None
    assert (await client.get("/users/me", headers=authorization)).status_code == 401
    response = await client.post("/auth/refresh", headers={**COOKIE_HEADERS, "Cookie": f"{COOKIE_NAME}={current_cookie}"})
    assert response.status_code == 401


async def test_refresh_reuse_revokes_only_the_affected_login(client, application):
    await register_and_login(client)
    old_cookie = client.cookies.get(COOKIE_NAME)
    refreshed = await client.post("/auth/refresh", headers=COOKIE_HEADERS)
    first_access = refreshed.json()["access_token"]
    async with httpx.AsyncClient(transport=httpx.ASGITransport(application), base_url="https://test") as other_device:
        login = await other_device.post("/auth/login", json={"email": PAYLOAD["email"], "password": PAYLOAD["password"]})
        other_access = login.json()["access_token"]
        replay = await client.post("/auth/refresh", headers={**COOKIE_HEADERS, "Cookie": f"{COOKIE_NAME}={old_cookie}"})
        assert replay.status_code == 401
        assert (await client.get("/users/me", headers={"Authorization": f"Bearer {first_access}"})).status_code == 401
        assert (await other_device.get("/users/me", headers={"Authorization": f"Bearer {other_access}"})).status_code == 200
        assert (await other_device.post("/auth/refresh", headers=COOKIE_HEADERS)).status_code == 200


async def test_refresh_csrf_and_expired_session(client, repository_session):
    await register_and_login(client)
    refresh_cookie = client.cookies.get(COOKIE_NAME)
    assert (await client.post("/auth/refresh")).status_code == 403
    assert (await client.post("/auth/logout", headers={**COOKIE_HEADERS, "Origin": "https://attacker.example"})).status_code == 403
    assert client.cookies.get(COOKIE_NAME) == refresh_cookie
    identity = get_token_service().decode_refresh_token(refresh_cookie)
    async with transaction(repository_session):
        await repository_session.execute(update(AuthSessionModel).where(AuthSessionModel.id == identity.session_id)
                                         .values(expires_at=datetime.now(UTC) - timedelta(seconds=1)))
    response = await client.post("/auth/refresh", headers=COOKIE_HEADERS)
    assert response.status_code == 401 and client.cookies.get(COOKIE_NAME) is None


async def test_failed_refresh_rolls_back_rotation(client, monkeypatch):
    await register_and_login(client)
    old_cookie = client.cookies.get(COOKIE_NAME)
    original_save = SQLAlchemyAuthSessionRepository.save

    async def fail_after_flush(self, session):
        await original_save(self, session)
        raise RuntimeError("Simulated failure after rotating the hash")

    with monkeypatch.context() as patch:
        patch.setattr(SQLAlchemyAuthSessionRepository, "save", fail_after_flush)
        with pytest.raises(RuntimeError):
            await client.post("/auth/refresh", headers=COOKIE_HEADERS)
    assert client.cookies.get(COOKIE_NAME) == old_cookie
    assert (await client.post("/auth/refresh", headers=COOKIE_HEADERS)).status_code == 200
