from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from app.schemas.user import Email


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: Email
    password: SecretStr = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
