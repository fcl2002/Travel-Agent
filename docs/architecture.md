# Backend structure

The backend lives in `app/`. Existing behavior is preserved while contracts,
entities, HTTP code, and database adapters have separate responsibilities.

```text
app/
  main.py                         # FastAPI application and ASGI entry point
  api/
    dependencies.py               # Wire concrete adapters to HTTP dependencies
    exception_handlers.py         # 404/409 mappings and safe validation errors
    endpoints/
      health.py                   # Existing /health and /health/db endpoints
      users.py                    # Create, list, read, update, and deactivate users
  core/
    config.py                     # Environment and .env settings
    exceptions.py                 # Application errors without database dependencies
    logging.py                    # Reserved; no logging implementation yet
    security.py                   # Argon2id password hashing and verification
  db/
    base.py                       # SQLAlchemy declarative Base and metadata
    session.py                    # Async engine and request-scoped AsyncSession
    probe.py                      # Async database health-check implementation
    tables/
      user.py                     # SQLAlchemy users table mapping
  models/
    user.py                       # User entity independent of SQLAlchemy
  repositories/
    user_repository.py            # Abstract UserRepository contract
    database_probe.py             # Database health-check contract
    sqlalchemy/
      user_repository.py          # SQLAlchemyUserRepository implementation
  schemas/
    user.py                       # UserCreate, UserUpdate, and public UserRead
    error.py                      # ErrorResponse for domain errors
  services/                       # Reserved for application services
agent/
  main.py
  tools.py
  states.py
alembic/
  env.py                          # Register table metadata and run migrations
  versions/0001_create_users.py    # Users migration
  versions/0002_add_user_update_at.py  # Last-update timestamp
```

## Responsibilities and database changes

`models/user.py` contains the pure Python `User` entity, with UUID, username,
email, a private password hash, creation time in UTC, the optional `update_at`
timestamp, and the active flag.
`core/exceptions.py` defines database-independent errors. Neither module imports
FastAPI or SQLAlchemy.

`repositories/user_repository.py` defines the contract using entities and Python
values. Future services can depend on this contract without knowing about database
sessions or ORM objects. The concrete SQLAlchemy implementation converts between
entities and table records, awaits queries, and translates uniqueness errors.
The contract's methods are asynchronous: callers use `await repository.add(user)`,
`await repository.get_by_id(id)`, and the same pattern for other operations.

SQLAlchemy details live in `db/` and `repositories/sqlalchemy/`. The mapping in
`db/tables/user.py` is deliberately separate from the entity in `models/user.py`.
`db/base.py` owns metadata. `db/session.py` creates the `AsyncEngine` and supplies
one `AsyncSession` per request through `get_session`. Sessions use
`expire_on_commit=False`, so returned entity fields remain available after commit.
The dependency closes each session when the request ends, and the application
disposes the engine's pool during shutdown. Sessions must not be shared between
concurrent tasks. Callers outside HTTP manage their own async session lifecycle.

`get_session` wraps each request in a single transaction. Dependency cleanup uses
FastAPI's function scope, so commit or rollback completes before the response is
sent. Every repository participating in a sequence must use the same session.

`api/dependencies.py` is the composition point for the existing HTTP dependencies.
Endpoint functions use repository and database-probe contracts, rather than
SQLAlchemy types. `get_user_repository` wires the concrete repository to the
request's shared transactional session.
Changing database technology can require changes to adapters, dependency wiring,
connection configuration, and migrations. It does not require rewriting the user
entity or repository contract. Database-specific integration tests also need to
follow the selected backend.

`core/logging.py` remains a placeholder; `services/` is reserved
for later application services. User routes currently coordinate the basic
repository calls directly. Authentication and ownership checks
are deferred; the routes have no authentication dependency.

`UserCreate` validates username, email, and `password`, represented by `SecretStr`.
The API hashes the password through `core/security.py` before creating the entity;
clients cannot supply `password_hash`. `UserUpdate` accepts only username and email, rejects
empty requests and explicit nulls, and leaves other fields under application
control. Both reject unknown fields. `UserRead` uses an explicit field allowlist
and attribute-based validation to return public entity data without the hash.
Domain errors are mapped to 404/409 using `ErrorResponse`. Invalid request data
returns the standard 422 error structure, excluding submitted values and error
context that could contain sensitive data.

## User repository behavior

The repository supports adding and updating users, lookups by UUID, username or
email, stable pagination, and deactivation. `deactivate(user_id)` sets `is_active`
to false and records the update time, preserving the stored record and its other
fields. Inactive users remain available in lookups and listings.
The repository does not expose physical deletion. Updates preserve id and creation
time. Missing lookups return `None`; updating or deactivating a missing user raises
`UserNotFoundError`.
`update_at` starts as `None`. Every repository update or deactivation assigns the
current time in UTC, ignoring an incoming update timestamp. This field records
the most recent operation, not a history of all changes. Its changes participate
in the same transaction and are reverted on rollback.
Unique-constraint violations raise `UserAlreadyExistsError`. Repository writes use
`flush()` to send changes to the database, without committing or rolling back the
sequence themselves. The outer transaction commits only after the entire sequence
succeeds. An exception escaping that block rolls back all its writes, including
earlier successful flushes. Handle the exception outside the transaction block.

Outside HTTP, start the transaction before the first database operation:

```python
from app.db.session import transaction
from app.repositories.sqlalchemy.user_repository import SQLAlchemyUserRepository

repository = SQLAlchemyUserRepository(session)
async with transaction(session):
    await repository.add(first_user)
    await repository.update(updated_user)
```

The HTTP dependency already opens this transaction; callers using its session
should not nest another `transaction(session)` around their operations.

Username and email matching is exact and case-sensitive. Usernames allow up to
255 characters, emails up to 320. The entity receives an already computed password
hash. `core/security.py` uses argon2-cffi's `PasswordHasher` with Argon2id and
library-default parameters, generating a random salt for every hash. It also
provides password verification, returning false for mismatches and invalid hashes.
Password whitespace is preserved; blank passwords are rejected by the input schema,
which currently accepts 1 to 512 characters. Hashing is run in a worker thread by
the async creation endpoint, keeping the core utility independent of FastAPI.
Passwords and hashes are excluded from public responses and validation errors.
No schema migration is needed because the existing hash column is reused.

## Running and testing

Start the API from the repository root:

```bash
python -m uvicorn app.main:app --reload
```

Run the unchanged agent using `python agent/main.py` after configuring its API keys.

Alembic imports `Base` from `app/db/base.py` and the table mapping from
`app/db/tables/user.py`. Run `python -m alembic upgrade head` to apply migrations.
The application uses Psycopg's async support with the existing
`postgresql+psycopg://` URL. The Alembic CLI keeps its synchronous connection;
async migration tests call Alembic through `AsyncConnection.run_sync`. No schema
migration is required for the switch to async sessions.
The `0002_add_user_update_at` migration adds the nullable timestamp column;
existing users retain `None` until their next update, preserving their data.

The default suite checks PostgreSQL and starts a real temporary Uvicorn server.
Repository tests use AnyIO with the asyncio backend and real async PostgreSQL
connections. They apply and revert migrations in isolated schemas, with savepoints
protecting their outer transactions. The schemas and test data are
rolled back afterward. Tests verify both successful commits and rollback of a
multi-operation sequence (deactivation followed by insertion) on uniqueness or
missing-user errors, reading the result
through a separate session. Two HTTP integration scenarios cover user lifecycle,
validation, error responses, Argon2id persistence, hash exclusion, and rollback after an update conflict
using the real PostgreSQL repository. Run `python -m pytest -m "not integration"` for the tests
that do not require PostgreSQL or a listening HTTP server.
