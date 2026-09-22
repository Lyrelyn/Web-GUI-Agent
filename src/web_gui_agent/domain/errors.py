"""Errors that have stable meanings independent of delivery adapters."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class ErrorCode(StrEnum):
    MODEL_INVALID_ACTION = "MODEL_INVALID_ACTION"
    LOCATOR_NOT_FOUND = "LOCATOR_NOT_FOUND"
    ACTION_TIMEOUT = "ACTION_TIMEOUT"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    BROWSER_CRASHED = "BROWSER_CRASHED"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    TASK_CANCELLED = "TASK_CANCELLED"
    TASK_NOT_FOUND = "TASK_NOT_FOUND"
    INVALID_STATE_TRANSITION = "INVALID_STATE_TRANSITION"
    VERSION_CONFLICT = "VERSION_CONFLICT"


class AgentError(BaseModel):
    """A serializable error safe to persist after sensitive data is removed."""

    model_config = ConfigDict(frozen=True)

    code: ErrorCode
    message: str
    retryable: bool = False


class DomainError(Exception):
    """Base exception for expected domain failures."""

    def __init__(self, error: AgentError) -> None:
        super().__init__(error.message)
        self.error = error


class TaskNotFoundError(DomainError):
    def __init__(self, task_id: str) -> None:
        super().__init__(
            AgentError(
                code=ErrorCode.TASK_NOT_FOUND,
                message=f"Task '{task_id}' does not exist.",
            )
        )


class InvalidStateTransitionError(DomainError):
    def __init__(self, current: str, target: str) -> None:
        super().__init__(
            AgentError(
                code=ErrorCode.INVALID_STATE_TRANSITION,
                message=f"Cannot transition task from {current} to {target}.",
            )
        )


class VersionConflictError(DomainError):
    def __init__(self, task_id: str) -> None:
        super().__init__(
            AgentError(
                code=ErrorCode.VERSION_CONFLICT,
                message=f"Task '{task_id}' was updated concurrently.",
                retryable=True,
            )
        )
