from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, Field


class ProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    configuration: dict = Field(default_factory=dict)
    make_primary: bool = False


class ProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    configuration: dict | None = None
    is_active: bool | None = None


class ProfileDuplicate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)


class ProfileOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    description: str
    configuration: dict
    is_primary: bool
    is_active: bool
    created_at: dt.datetime
    updated_at: dt.datetime

    model_config = {"from_attributes": True}


class ProfileDimensionsOut(BaseModel):
    dimensions: list[str]
    note: str


class ProfileCompletenessReport(BaseModel):
    profile_id: str
    name: str
    complete: bool
    filled: list[str]
    missing: list[str]
    score: float


class ProfileCompletenessOut(BaseModel):
    """Whether the caller has a profile the automations can actually use."""

    configured: bool
    profile_count: int
    detail: str
    #: the required fields, so the UI can render the checklist without
    #: hard-coding a copy of the backend rule
    required_fields: list[str]
    best: ProfileCompletenessReport | None = None
