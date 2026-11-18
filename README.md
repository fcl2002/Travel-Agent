# Travel Agent

## Overview

The Travel Agent  is an AI-powered application designed to help users find affordable transportation options within France.

The system aims to combine AI agents, ontologies, and external transportation data to identify suitable itineraries according to users' preferences, budgets, and travel constraints.

> **Status:** This project is currently under development. Suggestions, ideas, and contributions are very welcome. If you have any ideas for improving or expanding the project, feel free to contact me:
>
> - Email: `fcostalasmar@gmail.com`
> - LinkedIn: `https://www.linkedin.com/in/fernando-lasmar`
> - LinkedIn: `https://www.linkedin.com/in/vivian-fragoso`

## Backend setup

The backend follows a layered architecture. See
[architecture.md](docs/architecture.md) for responsibilities and the user repository.
The command-line agent is kept separately in `agent/`.

Use Python 3.14 (the version used to verify this setup). From the repository root:
If `.env` already exists, merge the example values into it before running these
commands; `cp -n` preserves an existing file.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
cp -n .env.example .env
# Generate a signing key only if .env does not already contain one.
python -c "import secrets; from dotenv import dotenv_values, set_key; dotenv_values('.env').get('JWT_SECRET_KEY') or set_key('.env', 'JWT_SECRET_KEY', secrets.token_urlsafe(32))"
docker compose up -d --wait db
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`, with interactive documentation
at `http://127.0.0.1:8000/docs` and a health check at
`http://127.0.0.1:8000/health`.

The backend uses FastAPI, SQLAlchemy asyncio, Uvicorn, Pydantic, pydantic-settings,
Alembic, and Psycopg 3. Database access uses a request-scoped `AsyncSession` and
repository methods are awaited. All operations sharing a request session belong
to one transaction: repositories flush changes, and the request commits only when
the complete sequence succeeds. An exception rolls back the whole sequence.
Outside HTTP, use `transaction(session)` from `app/db/session.py`.
The existing `postgresql+psycopg://` URL supports
both the asynchronous application and the synchronous Alembic CLI.
Development dependencies include pytest and AnyIO.
`GET /health` checks the API process; `GET /health/db` checks the database
connection and returns HTTP 503 when it is unavailable.

Configuration is loaded from environment variables or `.env`. The example
credentials are for local development. If you change PostgreSQL credentials,
update `DATABASE_URL` for local Python commands as well. Use URL-safe credentials
with the Compose URL template.

The existing command-line agent can be started with `python agent/main.py`
after configuring its API keys.

## User API

Registration is public. Login returns a JWT access token; account routes require
`Authorization: Bearer <access_token>` and allow access only to the caller's own
account. The Swagger **Authorize** button accepts the token returned by login.

| Method | Route | Purpose |
| --- | --- | --- |
| POST | `/users` | Create a user; returns 201 and a Location header |
| POST | `/auth/login` | Public login using email and password |
| POST | `/auth/refresh` | Rotate the refresh cookie and get a new access token |
| POST | `/auth/logout` | Revoke this login session and clear the cookie |
| GET | `/users/me` | Get the authenticated account |
| GET | `/users/{user_id}` | Get your own account; other IDs return 404 |
| PATCH | `/users/{user_id}` | Update your own username, email, and/or password |
| PATCH | `/users/{user_id}/deactivate` | Deactivate your own account without deleting it |

The global user-list endpoint is no longer exposed. There are no administrator
roles in this version, so a bearer token does not grant access to other accounts.

Example creation body:

```json
{
  "username": "traveler",
  "email": "traveler@example.com",
  "password": "A user supplied password1!"
}
```

Routes delegate user operations to `app/services/user_service.py`, which depends
on the repository contract and leaves transaction control to the shared session.
Creation and password updates receive `password` and compute an Argon2id hash in
the service with a random salt per hash. Hashing runs in a worker thread to avoid blocking the async
API. The repository receives only the resulting hash; clients cannot submit
`password_hash`. `app/core/security.py` provides `hash_password` and
`verify_password`. Registration, login, and password updates require passwords of
8–128 characters. Registration and password updates additionally require at least
one uppercase letter, one digit (0–9), and one ASCII punctuation character, such as
`!`, `@`, `#`, `$`, or `%`.
Whitespace is preserved and does not count as a special character. Login checks
length only, so existing accounts can authenticate with their original passwords.
Public responses contain `id`, `username`, `email`,
`created_at`, `update_at`, and `is_active`, with no password or hash fields.
Updates accept a nonempty subset of username/email/password; null values, unknown
fields, and client-supplied account metadata are rejected with 422. Missing users return
404 and duplicate usernames/emails return 409. Errors roll back the request's
transaction. Validation errors report field locations and messages without
echoing submitted values.

To change the authenticated user's password, send `PATCH /users/{user_id}` with
`Authorization: Bearer <access_token>` and a body such as
`{"password": "New password123!"}`. Only the account owner may update it.
The new password follows the same schema validation as registration and replaces
the stored hash; subsequent logins must use the new password.
The new password must differ from the current password. Reusing the current
password returns 400 and leaves all submitted account changes unapplied.

Login example:

```json
{"email": "traveler@example.com", "password": "A user supplied password1!"}
```

`POST /auth/login` returns `{"access_token": "...", "token_type": "bearer"}` and
sets a refresh cookie (`HttpOnly`, `SameSite=Strict`, path `/auth`). The refresh
token is never included in JSON or stored in `User`. A separate `auth_sessions`
table stores its SHA-256 hash, owner, expiry, and revocation state. Each login
creates an independent session.
Logging in with valid credentials reactivates an inactive account, sets
`is_active=true`, and updates `update_at`. Previous sessions are revoked so their
access and refresh tokens remain invalid after reactivation. Reactivation and
creation of the new session share one transaction; any failure rolls back both.
`JWT_SECRET_KEY` must be a cryptographically random secret of at least 32 bytes;
the API refuses to start without a valid key. The setup command above generates
one without printing it or replacing an existing key. Keep it out of version control.
Tokens use HS256 only, a UUID subject, issuer/audience validation, and expiration
after 15 minutes by default (`ACCESS_TOKEN_EXPIRE_MINUTES`, 1–120). They contain
no email, password, or hash. Wrong credentials and invalid tokens return a generic
401 with `WWW-Authenticate: Bearer`. Inactive accounts cannot use protected routes
or refresh sessions; they must log in again to reactivate. Each protected request
checks that both the user and login session are active, so logout, session
revocation, expiry, and user deactivation reject existing tokens.

For page reloads, the frontend calls `POST /auth/refresh` with `credentials: "include"`
and `X-Requested-With: XMLHttpRequest`, then keeps the new access token in memory.
The browser sends the refresh cookie automatically. Refresh tokens rotate on each
use and share an absolute seven-day session lifetime (`REFRESH_TOKEN_EXPIRE_DAYS`,
1–30); reuse of a superseded signed token revokes that login session.
Refresh/logout requests validate the Origin header when present and require the
custom header to protect cookie-based operations against CSRF.

`REFRESH_COOKIE_SECURE` defaults to true in application configuration. The local
`.env.example` uses false for HTTP development only; production must use true and
HTTPS. A separate same-site frontend may set `FRONTEND_ORIGIN` to its exact origin
for credentialed CORS; wildcards are rejected. Use a consistent hostname instead
of mixing `localhost` and `127.0.0.1`.
See [authentication.md](docs/authentication.md) for frontend bootstrap and logout.

Login and registration share a per-IP limit of 10 attempts per 60 seconds per
process; excess attempts return 429 and `Retry-After`. This limiter is bounded and
local to a worker. Production must use HTTPS and enforce a shared limit at the
trusted gateway if running multiple workers or instances. Forwarded client IPs
must only be trusted from your own proxy. Rotating the signing key invalidates
all previously issued access and refresh tokens. Tokens from before the session
implementation require a new login because they do not have a session ID.

## Docker and PostgreSQL

With Docker Desktop running, start the API and PostgreSQL 18:

```bash
docker compose up --build -d --wait
docker compose exec api python -m alembic upgrade head
```

The API listens at `http://127.0.0.1:8000/docs` and PostgreSQL at
`localhost:5433` (configurable with `POSTGRES_PORT`). Port 5433 avoids the existing
database on port 5432. Compose connects the API to the database using hostname `db`
and waits for PostgreSQL's health check before starting the API. The API runs as
a non-root user. Rebuild after source or dependency changes.

To run the API directly in Python while keeping PostgreSQL in Docker:

```bash
docker compose up -d db
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

Choose either the container API or the local API to use port 8000.

```bash
docker compose logs -f api
docker compose down
```

Database data persists in the `postgres_data` named volume after `down`.
PostgreSQL's initialization credentials apply only when that volume is first
created. No secrets or local virtual environment are copied into the image.

## Database migrations

[Alembic](https://alembic.sqlalchemy.org/en/latest/tutorial.html) uses the same
`DATABASE_URL` as the API. The initial migration creates `users` with UUID primary
keys, unique username and email, a password hash, a timezone-aware creation date,
and an active flag. The next migration adds `update_at`, the UTC timestamp of the
most recent update, deactivation, or reactivation. It is `None` until the first update, including
for existing users. Apply migrations with `python -m alembic upgrade head`.
Define future models using `Base` in `app/db/base.py`
and import their modules in `alembic/env.py` before generating a migration.

With PostgreSQL running and the local virtual environment active:

```bash
python -m alembic revision --autogenerate -m "Describe the schema change"
# Review the generated migration before applying it.
python -m alembic upgrade head
```

To apply migrations already included in a rebuilt API image:

```bash
docker compose exec api python -m alembic upgrade head
```

## Logs

Application logs use Python's built-in `logging` module and are emitted as JSON
to stdout. Set `LOG_LEVEL=INFO` in `.env` (the default), or choose `DEBUG`,
`WARNING`, `ERROR`, or `CRITICAL`. Request logs include the route template, method,
status, duration, and an ID returned in the `X-Request-ID` response header.
Lifecycle events, database health failures, and unexpected request errors are
also recorded. See [logging.md](docs/logging.md) for details and usage.

## Tests

With Docker Desktop running, start PostgreSQL and run the full suite:

```bash
docker compose up -d --wait db
python -m pytest
```

The suite focuses on API health behavior, the user repository, migrations, and
server startup. A single server test starts Uvicorn on an automatically assigned
local port, verifies `/health`, `/docs`, `/openapi.json`, and `/health/db` over HTTP,
then stops that process. The database endpoint connects to the real PostgreSQL
configured by `DATABASE_URL` (environment or `.env`). An existing server on port
8000 is not needed or changed.

PostgreSQL must be available: integration tests fail rather than skip when the
database is unavailable or `DATABASE_URL` points to a different database backend.
Repository tests cover a complete user lifecycle, atomic rollback of multiple
writes on duplicate username/email or missing-user errors, and migration
consistency and reversal. Deactivation sets `is_active` to false and preserves
the user's record. They use a
temporary PostgreSQL schema. The schema and its
data are rolled back after each test; the configured database user needs permission
to create schemas. The existing application tables are not changed by these tests.
No external API keys are required. The HTTP tests verify the Swagger page response,
not browser rendering or availability of external JavaScript and CSS files.

To run only the isolated API tests, without PostgreSQL or a network server:

```bash
python -m pytest -m "not integration"
```

To run only the PostgreSQL and server checks:

```bash
python -m pytest -m integration
```

## Documentation

See [architecture.md](docs/architecture.md) for the backend structure and
[config.md](docs/config.md) for Windows setup and agent commands.

The ontology designed to support the agent, including its underlying logic, concepts, and relationships, is described in **[ontology.md](docs/ontology.md)**.

## Current version

The current version is under development, with a focus on validating the agent's core architecture and its underlying ontology to support external data integration, the described [use cases](docs/ontology.md#1st-case), and future extensions.
