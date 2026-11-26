# Backend architecture decisions

This document records the decisions taken so far and why. It is intentionally
short: follow the links and the code to go deeper.

## 1. Layered architecture

```
api/ (routes, schemas, dependencies) -> services/ -> repositories/ (contracts)
                                                        ^
                              repositories/sqlalchemy/ + db/ (adapters)
```

- **Routes** convert HTTP to plain Python values and back. **Services** hold the
  business rules. **Repository contracts** describe persistence in domain terms;
  the SQLAlchemy adapters implement them.
- The `User` entity (`models/`) is separate from its table mapping (`db/tables/`)
  and imports neither FastAPI nor SQLAlchemy.
- **Why:** each rule has one obvious home, services can be read and tested without
  HTTP or a database, and changing the database touches only the adapters, the
  wiring in `api/dependencies.py`, and the migrations.
- **Trade-off:** more files than a single module; abstractions exist only at real
  boundaries.

## 2. Async database access

- SQLAlchemy asyncio with Psycopg 3, one `AsyncSession` per request.
- **Why:** the API is I/O-bound (database, password hashing in threads). Async lets
  one process serve many concurrent requests without a thread per request, and it
  matches FastAPI's async model.
- **Trade-offs:** CPU-heavy work must leave the event loop, so Argon2 runs in
  `asyncio.to_thread`. On Windows, async Psycopg needs the `SelectorEventLoop`
  (uvicorn uses it with `--reload`; the integration tests set it explicitly).
  Alembic stays synchronous: migrations are one-off scripts.

## 3. One transaction per request

- `get_session` opens one transaction per request. Repositories only `flush()`;
  they never commit or roll back.
- **Why:** multi-step operations (reactivation plus new session, password change
  plus revocation) must succeed or fail together; any exception rolls back the
  whole sequence. Outside HTTP, wrap the work in `transaction(session)`.
- One deliberate exception: when refresh detects a reused token, the service
  returns `None` instead of raising, so the revocation is committed, not undone.

## 4. PostgreSQL and migrations

- PostgreSQL in Docker for development; schema changes only through Alembic.
- **Why:** the database enforces uniqueness and row locks (`FOR UPDATE` on refresh),
  so these rules hold even under concurrent requests.
- Applied migrations are never edited. A correction is a new migration, as with
  `0004`, which renames `update_at` to `updated_at` in place without losing data.
- To add a change: define the model with `Base`, import it in `alembic/env.py`, run
  `python -m alembic revision --autogenerate -m "..."`, review the generated file,
  then `python -m alembic upgrade head`.

## 5. Authentication

- **Passwords:** Argon2id with a random salt. Login uses a dummy hash for unknown
  emails so response time does not reveal which accounts exist.
- **Access token:** short-lived JWT (15 minutes by default, HS256 only, issuer and
  audience checked) kept by the client in memory.
- **Refresh token:** stored in an HttpOnly cookie, rotated on every use, and kept in
  `auth_sessions` only as a SHA-256 hash. Reusing an old refresh token revokes that
  session.
- **Why sessions in the database:** a pure JWT cannot be revoked. Every access token
  is checked against its session, so logout, deactivation, and password changes
  take effect immediately.
- **Why a cookie for refresh:** JavaScript cannot read it, so an XSS bug cannot
  steal the long-lived token. Routes that use the cookie require
  `X-Requested-With` and a trusted `Origin` (`check_csrf`) to block cross-site
  requests. Details and the frontend flow: [authentication.md](authentication.md).

## 6. Authorization

- Account routes live under `/users/me`; no route takes a user ID.
- **Why:** with no ID in the path there is nothing to guess and no ownership check
  to forget when a new route is added.
- Changing email or password requires `current_password`, and a password change
  revokes every session. **Why:** a stolen 15-minute access token must not become
  a permanent account takeover.

## 7. Rate limiting

- In-process limiter: login and registration per client IP, account updates per
  account, 10 requests per 60 seconds, bounded memory.
- **Why:** slows brute force and Argon2 exhaustion without new infrastructure.
- **Limit:** it is per process. With several workers, or behind a gateway, set
  `FORWARDED_ALLOW_IPS` and add a shared limit at the gateway.

## 8. Configuration and logging

- Settings come from the environment or `.env` (pydantic-settings). The API refuses
  to start without a valid `JWT_SECRET_KEY`. **Why:** fail at startup, not at login.
- Logs are JSON with a field allowlist and a request ID; bodies, headers, cookies,
  and exception messages are never logged. **Why:** more people read logs than the
  database. See [logging.md](logging.md).

## 9. Tests

| Type | What it covers |
| --- | --- |
| Unit | Password policy and schemas, Argon2 hashing, JWT claims and rejection, rate-limiter expiry, logging, health endpoints without a database |
| Repository integration | User lifecycle and rollback of multi-step writes on real PostgreSQL |
| Migration | Models match migrations; full upgrade and downgrade keep data |
| API integration | Registration, login, `/users/me`, current-password checks, session revocation, refresh rotation and reuse, CSRF, rate limits, and rollback after failures |
| Server | A real uvicorn process starts and reaches PostgreSQL |

- **Why real PostgreSQL instead of mocks or SQLite:** the behavior under test
  (constraints, `FOR UPDATE`, error codes, transactions) is PostgreSQL behavior.
  Each test runs in a temporary schema and is rolled back, so the database user
  needs permission to create schemas.
- Run without a database: `python -m pytest -m "not integration"`.

## 10. Known limits

- Expired rows in `auth_sessions` are never deleted; a periodic cleanup will be
  needed as usage grows.
- Registration reveals whether an email is taken (409); accepted for an internal
  API until email verification exists.
