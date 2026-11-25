"""User entity, independent of persistence and HTTP frameworks."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4


@dataclass(frozen=True, kw_only=True)
class User:
    id: UUID
    username: str
    email: str
    password_hash: str = field(repr=False)
    created_at: datetime
    update_at: datetime | None = None
    is_active: bool = True

    def __post_init__(self) -> None:
        if not self.username.strip() or len(self.username) > 255:
            raise ValueError("Username must contain 1 to 255 characters.")
        if not self.email.strip() or len(self.email) > 320:
            raise ValueError("Email must contain 1 to 320 characters.")
        if not self.password_hash.strip():
            raise ValueError("Password hash must not be empty.")

    @classmethod
    def create(cls, *, username: str, email: str, password_hash: str) -> "User":
        """Accept an already hashed password; this entity does not hash passwords."""
        return cls(
            id=uuid4(), username=username, email=email,
            password_hash=password_hash, created_at=datetime.now(UTC),
        )
