"""Pydantic models defining the CAT 1.0 document format."""

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ErrorPolicy(StrEnum):
    STOP = "STOP"
    CONTINUE = "CONTINUE"
    RETRY = "RETRY"


class CATModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class TaskMetadata(CATModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=1000)
    created_at: datetime

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name must not be blank")
        return value.strip()

    @field_validator("created_at")
    @classmethod
    def created_at_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must include a timezone")
        return value.astimezone(timezone.utc)


class TaskSettings(CATModel):
    error_policy: ErrorPolicy = ErrorPolicy.STOP
    fail_safe: bool = True
    speed: float = Field(default=1.0, gt=0, le=10)
    retry_count: int = Field(default=0, ge=0, le=10)

    @model_validator(mode="after")
    def retry_requires_retry_policy(self) -> "TaskSettings":
        if self.retry_count and self.error_policy != ErrorPolicy.RETRY:
            raise ValueError("retry_count can only be set when error_policy is RETRY")
        if self.error_policy == ErrorPolicy.RETRY and self.retry_count < 1:
            raise ValueError("RETRY policy requires retry_count >= 1")
        return self


class Action(CATModel):
    id: int = Field(gt=0)
    command: str = Field(min_length=1, max_length=40, pattern=r"^[A-Z][A-Z0-9_]*$")
    params: dict[str, Any] = Field(default_factory=dict)


class CATTask(CATModel):
    format: Literal["CAT"]
    version: Literal["1.0"]
    id: UUID
    metadata: TaskMetadata
    settings: TaskSettings = Field(default_factory=TaskSettings)
    actions: list[Action] = Field(min_length=1, max_length=10000)

    @model_validator(mode="after")
    def action_ids_must_be_unique(self) -> "CATTask":
        ids = [action.id for action in self.actions]
        if len(ids) != len(set(ids)):
            raise ValueError("action ids must be unique")
        return self
