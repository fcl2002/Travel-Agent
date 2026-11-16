"""Request validation and public user responses."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import (
    BaseModel, ConfigDict, EmailStr, Field, SecretStr, StringConstraints,
    field_validator, model_validator,
)

Username = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
Email = Annotated[EmailStr, Field(max_length=320)]


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: Username
    email: Email
    password_hash: SecretStr = Field(
        min_length=1, max_length=512,
        description="Already computed password hash. No password hashing is performed by this API yet.",
    )

    @field_validator("password_hash")
    @classmethod
    def validate_password_hash(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("Password hash must not be empty")
        return value


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: Username | None = None
    email: Email | None = None

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
