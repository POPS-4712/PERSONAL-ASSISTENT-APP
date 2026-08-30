from __future__ import annotations

import datetime as dt
import uuid
from typing import Literal

from pydantic import BaseModel, Field

CredentialTypeIn = Literal["api_key", "bearer", "basic_auth", "oauth2", "custom"]


class CredentialCreate(BaseModel):
    provider: str = Field(min_length=1, max_length=64, examples=["openai"])
    name: str = Field(min_length=1, max_length=120, examples=["OpenAI production"])
    type: CredentialTypeIn = "api_key"
    # The secret material. Never echoed back. Shape depends on `type`:
    #  api_key/bearer -> {"api_key": "..."}  | basic_auth -> {"username","password"}
    #  oauth2 -> {"access_token","refresh_token"?}  | custom -> free-form
    secret: dict = Field(examples=[{"api_key": "sk-..."}])
    # Public, non-secret hints for the connection test, e.g.
    # {"test_url": "https://api.example.com/v1/me", "header_name": "X-Api-Key"}
    meta: dict = Field(default_factory=dict)


class CredentialUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    secret: dict | None = None
    meta: dict | None = None
    is_enabled: bool | None = None


class CredentialOut(BaseModel):
    """Metadata only. `encrypted_data` and the plaintext secret are never here."""

    id: uuid.UUID
    provider: str
    name: str
    type: str
    status: str
    hint: str
    meta: dict
    is_enabled: bool
    last_tested_at: dt.datetime | None
    last_used_at: dt.datetime | None
    created_at: dt.datetime
    updated_at: dt.datetime

    model_config = {"from_attributes": True}


class CredentialTestOut(BaseModel):
    ok: bool
    detail: str
    latency_ms: float | None
    status: str
