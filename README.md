# Travel Agent

## Overview

The Travel Agent  is an AI-powered application designed to help users find affordable transportation options within France.

The system aims to combine AI agents, ontologies, and external transportation data to identify suitable itineraries according to users' preferences, budgets, and travel constraints.

This repository contains the backend API (FastAPI, PostgreSQL, SQLAlchemy) that handles user accounts and authentication, and the command-line agent in `agent/`.

> **Status:** This project is currently under development. Suggestions, ideas, and contributions are very welcome. If you have any ideas for improving or expanding the project, feel free to contact me:
>
> - LinkedIn: `linkedin.com/in/fernando-lasmar`
> - LinkedIn: `linkedin.com/in/vivian-fragoso`

## Prerequisites

- Python 3.14
- Docker Desktop, for PostgreSQL

## Setup

From the repository root, create a virtual environment and install the dependencies
(on Windows, see [config.md](docs/config.md)):

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

Create your local `.env` from the example. `cp -n` keeps an existing file; if you
already have one, merge in any new keys from `.env.example`.

```bash
cp -n .env.example .env
```

Generate the JWT signing key. The command does nothing if `.env` already has one:

```bash
python -c "import secrets; from dotenv import dotenv_values, set_key; dotenv_values('.env').get('JWT_SECRET_KEY') or set_key('.env', 'JWT_SECRET_KEY', secrets.token_urlsafe(32))"
```

Keep `.env` out of version control. The example credentials only work against the
local PostgreSQL container.

## Run

Start PostgreSQL, apply the migrations, and start the API:

```bash
docker compose up -d --wait db
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

Open the interactive API documentation at `http://127.0.0.1:8000/docs`. Create a
user, log in with `POST /auth/login`, and paste the returned access token into the
**Authorize** button to call the protected routes. `GET /health` and
`GET /health/db` check the API and the database.

To run the API in Docker as well:

```bash
docker compose up --build -d --wait
docker compose exec api python -m alembic upgrade head
```

Use either the local API or the container API, since both use port 8000. Stop
everything with `docker compose down`; data persists in the `postgres_data` volume,
and PostgreSQL applies its initial credentials only when that volume is first created.

The command-line agent runs with `python agent/main.py` after setting its API keys
in `.env`.

## Tests

With PostgreSQL running:

```bash
python -m pytest
```

Integration tests fail rather than skip when PostgreSQL is unavailable. To run only
the tests that need neither PostgreSQL nor a server:

```bash
python -m pytest -m "not integration"
```

## Documentation

- [architecture.md](docs/architecture.md): backend layers, database, migrations, and tests
- [authentication.md](docs/authentication.md): login, refresh, logout, frontend integration, rate limits, and deployment
- [logging.md](docs/logging.md): log format and configuration
- [config.md](docs/config.md): Windows setup and agent commands
- [ontology.md](docs/ontology.md): the ontology behind the agent, its concepts, and relationships

Routes, request bodies, and responses are documented in the OpenAPI schema at `/docs`.

## Current version

The current version is under development, with a focus on validating the agent's core architecture and its underlying ontology to support external data integration, the described [use cases](docs/ontology.md#1st-case), and future extensions.
