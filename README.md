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
most recent update or deactivation. It is `None` until the first update, including
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
