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

Use Python 3.14 (the version used to verify this setup). From the repository root:
If `.env` already exists, merge the example values into it before running these
commands; `cp -n` preserves an existing file.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
cp -n .env.example .env
python -m uvicorn src.api:app --reload
```

The API is available at `http://127.0.0.1:8000`, with interactive documentation
at `http://127.0.0.1:8000/docs` and a health check at
`http://127.0.0.1:8000/health`.

The backend uses FastAPI, SQLAlchemy, Uvicorn, Pydantic, pydantic-settings,
Alembic, and Psycopg 3. Development dependencies include pytest.
`GET /health` checks the API process; `GET /health/db` checks the database
connection and returns HTTP 503 when it is unavailable.

Configuration is loaded from environment variables or `.env`. The example
credentials are for local development. If you change PostgreSQL credentials,
update `DATABASE_URL` for local Python commands as well. Use URL-safe credentials
with the Compose URL template.

The existing command-line agent can still be started with `python src/main.py`
after configuring its API keys.

## Docker and PostgreSQL

With Docker Desktop running, start the API and PostgreSQL 18:

```bash
docker compose up --build -d --wait
```

The API listens at `http://127.0.0.1:8000/docs` and PostgreSQL at
`localhost:5433` (configurable with `POSTGRES_PORT`). Port 5433 avoids the existing
database on port 5432. Compose connects the API to the database using hostname `db`
and waits for PostgreSQL's health check before starting the API. The API runs as
a non-root user. Rebuild after source or dependency changes.

To run the API directly in Python while keeping PostgreSQL in Docker:

```bash
docker compose up -d db
python -m uvicorn src.api:app --reload
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
`DATABASE_URL` as the API. There are no application tables or revisions yet.
Define future models using `Base` in `src/database.py` and import their modules
in `alembic/env.py` before generating a migration.

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

```bash
python -m pytest
```

The tests use SQLite and do not require Docker, PostgreSQL, or external API keys.

## Documentation

The travel agent will be fully documented in Markdown files and accessible via the **[documentation.md](docs/documentation.md)** folder in this repository.

The ontology designed to support the agent, including its underlying logic, concepts, and relationships, is described in **[ontology.md](docs/ontology.md)**.

## Current version

The current version is under development, with a focus on validating the agent's core architecture and its underlying ontology to support external data integration, the described [use cases](docs/ontology.md#1st-case), and future extensions.
