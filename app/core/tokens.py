"""JWT signing and strict validation, independent of HTTP and persistence."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt

from app.core.exceptions import AuthenticationError

MAX_ACCESS_TOKEN_MINUTES = 120
MAX_TOKEN_LENGTH = 4096  # Reject oversized input before spending CPU on decoding.


@dataclass(frozen=True)
class TokenIdentity:
    user_id: UUID
    session_id: UUID


class JWTTokenService:
    def __init__(self, *, secret: str, expires_minutes: int = 15,
                 issuer: str = "travel-agent", audience: str = "travel-agent-api"):
        if not secret.strip() or len(secret.encode()) < 32:
            raise ValueError("JWT signing key must contain at least 32 bytes")
        if (not 1 <= expires_minutes <= MAX_ACCESS_TOKEN_MINUTES
                or not issuer.strip() or not audience.strip()):
            raise ValueError(
                f"JWT requires a 1-{MAX_ACCESS_TOKEN_MINUTES} minute lifetime and nonempty issuer and audience"
            )
        self._secret = secret
        self.expires_minutes = expires_minutes
        self.issuer = issuer
        self.audience = audience

    def _encode(self, user_id: UUID, session_id: UUID, token_use: str,
                expires_at: datetime | None = None) -> str:
        now = datetime.now(UTC)
        return jwt.encode({
            "sub": str(user_id), "sid": str(session_id), "jti": str(uuid4()),
            "iat": now, "exp": expires_at or now + timedelta(minutes=self.expires_minutes),
            "iss": self.issuer, "aud": self.audience, "token_use": token_use,
        }, self._secret, algorithm="HS256")

    def create_access_token(self, user_id: UUID, session_id: UUID) -> str:
        return self._encode(user_id, session_id, "access")

    def create_refresh_token(self, user_id: UUID, session_id: UUID, expires_at: datetime) -> str:
        return self._encode(user_id, session_id, "refresh", expires_at)

    def _decode(self, token: str, token_use: str) -> TokenIdentity:
        if len(token) > MAX_TOKEN_LENGTH:
            raise AuthenticationError()
        try:
            claims = jwt.decode(
                token, self._secret, algorithms=["HS256"],
                issuer=self.issuer, audience=self.audience,
                options={"require": ["sub", "sid", "jti", "iat", "exp", "iss", "aud", "token_use"],
                         "strict_aud": True},
            )
            if claims["token_use"] != token_use:
                raise AuthenticationError()
            UUID(claims["jti"])
            return TokenIdentity(UUID(claims["sub"]), UUID(claims["sid"]))
        except (jwt.InvalidTokenError, ValueError, TypeError, AttributeError):
            raise AuthenticationError() from None

    def decode_access_token(self, token: str) -> TokenIdentity:
        return self._decode(token, "access")

    def decode_refresh_token(self, token: str) -> TokenIdentity:
        return self._decode(token, "refresh")
