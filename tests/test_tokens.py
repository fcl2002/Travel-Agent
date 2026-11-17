from datetime import UTC, datetime, timedelta
import secrets
from uuid import uuid4

import jwt
import pytest

from app.core.exceptions import AuthenticationError
from app.core.tokens import JWTTokenService


def test_access_token_claims_and_signing_configuration():
    key = secrets.token_urlsafe(64)
    service = JWTTokenService(secret=key, expires_minutes=15)
    user_id = uuid4()
    session_id = uuid4()
    token = service.create_access_token(user_id, session_id)
    identity = service.decode_access_token(token)
    assert (identity.user_id, identity.session_id) == (user_id, session_id)
    claims = jwt.decode(token, key, algorithms=["HS256"], audience=service.audience, issuer=service.issuer)
    assert set(claims) == {"sub", "sid", "jti", "iat", "exp", "iss", "aud", "token_use"}
    assert claims["exp"] - claims["iat"] == 900 and claims["token_use"] == "access"
    with pytest.raises(ValueError):
        JWTTokenService(secret="short-key")
    refresh = service.create_refresh_token(user_id, session_id, datetime.now(UTC) + timedelta(days=7))
    assert service.decode_refresh_token(refresh) == identity
    for decoder, invalid_token in ((service.decode_access_token, refresh), (service.decode_refresh_token, token)):
        with pytest.raises(AuthenticationError):
            decoder(invalid_token)


def test_invalid_access_tokens_are_rejected():
    key = secrets.token_urlsafe(64)
    service = JWTTokenService(secret=key, expires_minutes=15)
    now = datetime.now(UTC)
    claims = {"sub": str(uuid4()), "sid": str(uuid4()), "jti": str(uuid4()),
              "iat": now, "exp": now + timedelta(minutes=15),
              "iss": service.issuer, "aud": service.audience, "token_use": "access"}
    invalid_claims = [
        {**claims, "exp": now - timedelta(seconds=1)},
        {**claims, "iat": now + timedelta(minutes=5)},
        {**claims, "iss": "another-issuer"}, {**claims, "aud": "another-audience"},
        {**claims, "token_use": "refresh"}, {**claims, "sub": "not-a-uuid"},
        {name: value for name, value in claims.items() if name != "exp"},
    ]
    tokens = [jwt.encode(payload, key, algorithm="HS256") for payload in invalid_claims]
    tokens += [jwt.encode(claims, secrets.token_urlsafe(64), algorithm="HS256"),
               jwt.encode(claims, key, algorithm="HS512"), jwt.encode(claims, "", algorithm="none"),
               "malformed", "x" * 4097]
    for token in tokens:
        with pytest.raises(AuthenticationError):
            service.decode_access_token(token)
