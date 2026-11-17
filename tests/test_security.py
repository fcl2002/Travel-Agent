import pytest

from app.core.exceptions import AuthRateLimitError
from app.core.rate_limit import AuthRateLimiter
from app.core.security import hash_password, verify_password


def test_argon2_hashing_and_verification():
    password = "  Uma senha com café!  "
    password_hash = hash_password(password)
    assert password_hash.startswith("$argon2id$")
    assert hash_password(password) != password_hash
    assert verify_password(password, password_hash) is True
    assert verify_password(password.strip(), password_hash) is False
    assert verify_password("wrong-password", password_hash) is False
    assert verify_password(password, "invalid-hash") is False


def test_auth_rate_limit_expires_and_bounds_client_storage(monkeypatch):
    now = [0]
    monkeypatch.setattr("app.core.rate_limit.monotonic", lambda: now[0])
    limiter = AuthRateLimiter(limit=1, window_seconds=60, max_clients=1)
    limiter.check("first-client")
    for client in ("first-client", "second-client"):
        with pytest.raises(AuthRateLimitError):
            limiter.check(client)
    now[0] = 61
    limiter.check("second-client")
