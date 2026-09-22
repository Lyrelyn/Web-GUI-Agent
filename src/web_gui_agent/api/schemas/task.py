"""HTTP-specific task payloads; domain models remain transport-neutral."""

from datetime import datetime
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator

from web_gui_agent.domain.task import Task, TaskInput, TaskOptions, TaskStatus


class CreateTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instruction: str = Field(min_length=1, max_length=10_000)
    start_url: str | None = Field(default=None, max_length=2_083)
    context: dict[str, str] = Field(default_factory=dict)
    options: TaskOptions | None = None

    @field_validator("instruction")
    @classmethod
    def instruction_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Instruction must not be blank.")
        return value

    @field_validator("start_url")
    @classmethod
    def start_url_must_be_http_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("start_url must be an absolute http or https URL.")
        return value

    def to_domain(self) -> TaskInput:
        values: dict[str, object] = {
            "instruction": self.instruction,
            "start_url": self.start_url,
            "context": self.context,
        }
        if self.options is not None:
            values["options"] = self.options
        return TaskInput.model_validate(values)


class TaskResponse(BaseModel):
    id: str
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    version: int

    @classmethod
    def from_domain(cls, task: Task) -> "TaskResponse":
        return cls(
            id=task.id,
            status=task.status,
            created_at=task.created_at,
            updated_at=task.updated_at,
            version=task.version,
        )


class ErrorResponse(BaseModel):
    code: str
    message: str
