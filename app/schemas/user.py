"""Request validation and public user responses."""

from datetime import datetime
from string import punctuation
from typing import Annotated
from uuid import UUID

from pydantic import (
    AfterValidator, BaseModel, ConfigDict, EmailStr, Field, SecretStr, StringConstraints,
    model_validator,
)

Username = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
Email = Annotated[EmailStr, Field(max_length=320)]


def validate_password(value: SecretStr) -> SecretStr:
    password = value.get_secret_value()
    if not password.strip():
        raise ValueError("Password must not be empty")
    if not any(character.isupper() for character in password):
        raise ValueError("Password must contain at least one uppercase letter")
    if not any(character in "0123456789" for character in password):
        raise ValueError("Password must contain at least one digit (0-9)")
    if not any(character in punctuation for character in password):
        raise ValueError("Password must contain at least one special character (e.g. !@#$%)")
    return value


Password = Annotated[
    SecretStr,
    Field(
        min_length=8, max_length=128,
        description=(
            "8–128 characters, including at least one uppercase letter, one digit "
            "(0–9), and one ASCII punctuation character (e.g. !@#$%). "
            "Hashed with Argon2id; never returned in API responses."
        ),
    ),
    AfterValidator(validate_password),
]


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: Username
    email: Email
    password: Password


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: Username | None = None
    email: Email | None = None
    password: Password | None = None

    @model_validator(mode="after")
    def validate_changes(self) -> "UserUpdate":
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update")
        if any(getattr(self, name) is None for name in self.model_fields_set):
            raise ValueError("Updated fields must not be null")
        return self


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    email: str
    created_at: datetime
    update_at: datetime | None
    is_active: bool
