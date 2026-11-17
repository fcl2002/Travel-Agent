from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class AuthSession:
    id: UUID
    user_id: UUID
    refresh_token_hash: str = field(repr=False)
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None

    def is_active(self, now: datetime) -> bool:
        return self.revoked_at is None and self.expires_at > now


@dataclass(frozen=True, kw_only=True)
class AuthTokens:
    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    refresh_expires_at: datetime
