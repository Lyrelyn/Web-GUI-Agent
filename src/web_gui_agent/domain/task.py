"""Task input, lifecycle, and transition rules."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Self
from urllib.parse import urlparse
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from web_gui_agent.domain.errors import InvalidStateTransitionError


class TaskStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    NEEDS_CONFIRMATION = "NEEDS_CONFIRMATION"


TERMINAL_TASK_STATUSES = frozenset(
    {
        TaskStatus.SUCCEEDED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
        TaskStatus.NEEDS_CONFIRMATION,
    }
)

_ALLOWED_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.QUEUED: frozenset({TaskStatus.RUNNING, TaskStatus.CANCELLED}),
    TaskStatus.RUNNING: TERMINAL_TASK_STATUSES,
    TaskStatus.SUCCEEDED: frozenset(),
    TaskStatus.FAILED: frozenset(),
    TaskStatus.CANCELLED: frozenset(),
    TaskStatus.NEEDS_CONFIRMATION: frozenset(),
}


class TaskOptions(BaseModel):
    model_config = ConfigDict(frozen=True)

    timeout_ms: int = Field(default=120_000, ge=1_000, le=600_000)
    max_retries: int = Field(default=2, ge=0, le=10)


class TaskInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    instruction: str = Field(min_length=1, max_length=10_000)
    start_url: str | None = Field(default=None, max_length=2_083)
    context: dict[str, str] = Field(default_factory=dict)
    options: TaskOptions = Field(default_factory=TaskOptions)

    @field_validator("instruction")
    @classmethod
    def instruction_must_not_be_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Instruction must not be blank.")
        return normalized

    @field_validator("start_url")
    @classmethod
    def start_url_must_be_http_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("start_url must be an absolute http or https URL.")
        return value


class Task(BaseModel):
    """Persisted unit of work with optimistic-concurrency version."""

    model_config = ConfigDict(frozen=True)

    id: str
    input: TaskInput
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    version: int = Field(ge=0)

    @classmethod
    def queued(cls, task_input: TaskInput, now: datetime | None = None) -> Self:
        timestamp = now or datetime.now(UTC)
        return cls(
            id=str(uuid4()),
            input=task_input,
            status=TaskStatus.QUEUED,
            created_at=timestamp,
            updated_at=timestamp,
            version=0,
        )

    def transition_to(self, target: TaskStatus, now: datetime) -> Self:
        if target not in _ALLOWED_TRANSITIONS[self.status]:
            raise InvalidStateTransitionError(self.status, target)
        return self.model_copy(
            update={"status": target, "updated_at": now, "version": self.version + 1}
        )
