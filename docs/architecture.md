# Backend structure

The backend lives in `app/`. Existing behavior is preserved while contracts,
entities, HTTP code, and database adapters have separate responsibilities.

```text
app/
  main.py                         # FastAPI application and ASGI entry point
  api/
    dependencies.py               # Wire concrete adapters to HTTP dependencies
    exception_handlers.py         # Authentication/domain errors and safe validation errors
    middleware.py                 # HTTP request timing, status, and request ID logging
    endpoints/
      health.py                   # Existing /health and /health/db endpoints
      users.py                    # Registration and self-only account management
      auth.py                     # JSON login endpoint
    auth_cookies.py               # Refresh cookie attributes and clearing
  core/
    config.py                     # Environment and .env settings
    exceptions.py                 # Application errors without database dependencies
    logging.py                    # JSON logging and request context using standard logging
    security.py                   # Argon2id password hashing and verification
    tokens.py                     # JWT signing, claims, signature, and expiry validation
    rate_limit.py                 # Bounded per-process authentication throttling
  db/
    base.py                       # SQLAlchemy declarative Base and metadata
    session.py                    # Async engine and request-scoped AsyncSession
    probe.py                      # Async database health-check implementation
    tables/
      user.py                     # SQLAlchemy users table mapping
      auth_session.py             # Session owner, refresh hash, expiry, revocation
  models/
    user.py                       # User entity independent of SQLAlchemy
    auth_session.py               # AuthSession and private token-pair result
  repositories/
    user_repository.py            # Abstract UserRepository contract
    auth_session_repository.py    # Abstract login-session persistence contract
    database_probe.py             # Database health-check contract
    sqlalchemy/
      user_repository.py          # SQLAlchemyUserRepository implementation
      auth_session_repository.py  # Session persistence and locked refresh reads
  schemas/
    user.py                       # UserCreate, UserUpdate, and public UserRead
    error.py                      # ErrorResponse for domain errors
    auth.py                       # LoginRequest and TokenResponse
  services/
    user_service.py               # User operations and password-hashing coordination
    auth_service.py               # Credentials and active-user token resolution
agent/
  main.py
  tools.py
  states.py
alembic/
  env.py                          # Register table metadata and run migrations
  versions/0001_create_users.py    # Users migration
  versions/0002_add_user_update_at.py  # Last-update timestamp
  versions/0003_create_auth_sessions.py  # Refresh-session storage
  versions/0004_rename_users_updated_at.py  # Rename update_at to updated_at
```

## Responsibilities and database changes

`models/user.py` contains the pure Python `User` entity, with UUID, username,
email, a private password hash, creation time in UTC, the optional `updated_at`
timestamp, and the active flag.
`core/exceptions.py` defines database-independent errors. Neither module imports
FastAPI or SQLAlchemy.

`repositories/user_repository.py` defines the contract using entities and Python
values. `UserService` depends on this contract without knowing about database
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
User endpoints depend on `UserService` and authenticated user dependencies;
health endpoints use the database-probe
contract. `get_user_repository` wires the concrete repository to the request's
shared transactional session, and `get_user_service` injects that repository
into the service. SQLAlchemy details stay out of both user routes and the service.
Changing database technology can require changes to adapters, dependency wiring,
connection configuration, and migrations. It does not require rewriting the user
entity or repository contract. Database-specific integration tests also need to
follow the selected backend.

`UserService` coordinates creation, retrieval, pagination, partial updates, and
deactivation. It creates the entity, computes Argon2id hashes through the core
utility in a worker thread, and raises `UserNotFoundError` for missing lookups.
It accepts ordinary Python values and returns entities; it does not import HTTP
schemas, FastAPI, or SQLAlchemy. Routes handle request/response conversion and
HTTP metadata, while schemas validate incoming data. The service does not open,
commit, or roll back transactions: the existing session boundary owns the entire
operation sequence.

`AuthService` uses user/session repository contracts and `JWTTokenService`, without FastAPI
or SQLAlchemy dependencies. It verifies Argon2 credentials in a worker thread,
uses a dummy hash for unknown emails, and returns the same authentication failure
for wrong passwords or missing users. Valid credentials reactivate an inactive
user through the existing user repository update, updating `updated_at` and revoking
all prior sessions through the session repository. Successful login persists
an independent auth session and returns an access/refresh pair internally. The
route returns only the access token in JSON and sets the refresh token in a cookie.
Token validation checks both session state and user state on every protected request.
Reactivation, revocation of prior sessions, and creation of the new session share
the request transaction, so a failure rolls back the entire sequence. Inactive
accounts cannot access protected routes or refresh sessions; only a login with
valid credentials reactivates the account. Prior tokens remain invalid afterward.

`get_current_user` extracts a bearer token and calls the auth service.
`get_owned_user` additionally compares the requested UUID with the authenticated
user, returning 404 for another account without looking up its existence. Routes
for account reads, updates, and deactivation require these dependencies. Registration
is public; the global listing route is not exposed because there is no admin role.
The internal repository/service listing methods remain available to trusted code.
`core/logging.py` configures the `app` logger using Python's standard `logging`
module. Application logs go to stdout as JSON, with their minimum severity set by
`LOG_LEVEL` (default `INFO`). Uvicorn and third-party loggers keep their own
configuration. `api/middleware.py` assigns a request ID in a `ContextVar`, adds
`X-Request-ID` to responses, and logs the route template, method, HTTP status, and
duration. It resets the context after each request. Unknown routes use
`<unmatched>` so their raw paths do not enter application logs. Headers, cookies,
query strings, bodies, and account data are not collected. Unexpected exceptions
log their type and traceback locations, omitting exception messages and source
lines that could contain credentials or SQL parameters. Their responses contain a
generic 500 error and the request ID. Lifecycle and database health-check events
are also logged. See [logging.md](logging.md) for usage and examples.

`UserCreate` validates username, email, and `password`, represented by `SecretStr`.
The service hashes the password through `core/security.py` before creating the entity;
clients cannot supply `password_hash`. `UserUpdate` accepts only username and email, rejects
empty requests and explicit nulls, and leaves other fields under application
control. Both reject unknown fields. `UserRead` uses an explicit field allowlist
and attribute-based validation to return public entity data without the hash.
Domain errors are mapped to 401/404/409/429 using `ErrorResponse`. Authentication
failures include `WWW-Authenticate: Bearer`; throttling includes `Retry-After`.
Token responses and authenticated account responses use `Cache-Control: no-store`.
Invalid request data
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
`updated_at` starts as `None`. Every repository update or deactivation assigns the
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
Registration and login schemas accept passwords of 8 to 128 characters, inclusive.
Registration additionally requires at least one uppercase letter, one digit (0–9),
and one ASCII punctuation character (for example, `!`, `@`, `#`, `$`, or `%`).
Password whitespace is preserved and does not count as a special character.
Login validates length only to allow existing accounts to authenticate with their
original passwords. Invalid registration passwords and password lengths outside
these bounds return 422 before the request reaches the service.
Hashing is run in a worker thread by
the async user service using `asyncio.to_thread`, keeping the service and core
utility independent of FastAPI.
Passwords and hashes are excluded from public responses and validation errors.
No schema migration is needed because the existing hash column is reused.

## JWT configuration and boundaries

`core/tokens.py` uses PyJWT with a fixed HS256 allowlist and requires `sub`, `sid`,
`jti`, `iat`, `exp`, `iss`, `aud`, and `token_use`. Access/refresh decoders require
the corresponding token type, preventing token substitution. Subject, session ID,
and token ID must be UUIDs; each token gets a new random token ID.
Issuer and audience come from trusted configuration, never token headers.
The signing key is supplied through `JWT_SECRET_KEY` and must have at least 32
bytes. It has no hardcoded or generated-at-startup fallback. The API validates
configuration during startup; database-only Alembic operations do not need the key.
The API's default access lifetime is 15 minutes, configurable from 1 to 120 minutes.
The token helper's existing 120-minute default is preserved, while API wiring
always supplies the configured lifetime.

Use the README command to create a cryptographically random key once. Existing
keys are preserved; replacing a key and restarting the server invalidates all old
tokens. Tokens carry only account UUID and token metadata, never credentials or
email. Session-backed refresh tokens have an absolute seven-day lifetime by
default (configurable to 1–30 days). Refreshes do not extend that deadline.

`auth_sessions` holds one row per login, separate from `users`: UUID, owner UUID,
SHA-256 digest of the latest refresh JWT, creation time, expiry, and optional
revocation time. The signed refresh JWT has a high-entropy signature and random
token ID, so a fast cryptographic digest is appropriate; passwords still use Argon2.
No raw access or refresh token is persisted. Every access JWT is bound to its
session ID, allowing logout and replay detection to reject its access tokens too.

Refresh takes a `FOR UPDATE` lock on the session row, checks its digest, rotates
the refresh token, and flushes the new digest in the same outer transaction. A
validly signed old refresh token proves reuse and revokes the session. The service
returns a failure result rather than raising after revocation, so the HTTP 401
response commits that revocation instead of rolling it back. Ordinary failures
still roll back; a failed rotation leaves the previous cookie valid.

Cookies are HttpOnly, SameSite=Strict, host-only, path `/auth`, and Secure by default.
Local HTTP development explicitly sets `REFRESH_COOKIE_SECURE=false`; production
must use HTTPS and true. Refresh/logout require `X-Requested-With: XMLHttpRequest`
and validate Origin against the API origin or one configured `FRONTEND_ORIGIN`.
Credentialed CORS is enabled only for that exact origin, without wildcard support.
See [authentication.md](authentication.md) for browser integration and concurrent
refresh considerations. Expired session rows may be removed by a periodic maintenance
task after their absolute expiry; no background scheduler is added here.

`AuthRateLimiter` applies a shared 10-attempt/60-second budget to registration and
login by client IP. Storage is capped at 10000 client entries; exhausted capacity
fails closed rather than allocating unlimited memory. Expired entries are removed.
This limit is per process and resets on restart. Use HTTPS and a trusted gateway
with a shared limiter for production deployments with multiple workers/replicas;
only trust forwarded headers from explicitly configured proxy addresses.

The validation follows [PyJWT's documented claim and algorithm validation](https://pyjwt.readthedocs.io/en/latest/api.html)
and the [OWASP JWT guidance](https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_Cheat_Sheet.html).

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
`0004_rename_users_updated_at` renames that column from `update_at` to `updated_at`
in place, so existing values are kept.

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
Authentication tests cover token claims, expired/forged/wrong-algorithm tokens,
generic credential failures, cross-account access, deactivation, login reactivation,
revocation of prior sessions, rollback after a failed reactivation, and throttling.
Refresh tests cover cookie flags, hash-only storage, rotation, replay revocation,
device isolation, logout, CSRF, session expiry, and rollback after a failed write.
Tests generate an ephemeral signing key in the environment; they never need a
personal JWT secret and never write test keys to `.env`.
