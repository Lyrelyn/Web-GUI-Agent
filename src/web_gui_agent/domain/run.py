"""Execution records persisted by later workflow phases."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from web_gui_agent.domain.action import Action, ToolResult, VerificationResult
from web_gui_agent.domain.errors import AgentError
from web_gui_agent.domain.observation import Observation
from web_gui_agent.domain.task import Task


class RunPhase(StrEnum):
    OBSERVE = "OBSERVE"
    PLAN = "PLAN"
    EXECUTE = "EXECUTE"
    VERIFY = "VERIFY"


class StepRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    index: int = Field(ge=0)
    phase: RunPhase
    observation: Observation | None = None
    observation_artifact_id: str | None = None
    action: Action | None = None
    tool_result: ToolResult | None = None
    verification: VerificationResult | None = None
    duration_ms: int = Field(ge=0)
    error: AgentError | None = None


class MemoryValue(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: Any
    source_step: int = Field(ge=0)


SharedMemory = dict[str, MemoryValue]


class RunOutcome(BaseModel):
    """In-memory result of one phase-2 browser execution."""

    model_config = ConfigDict(frozen=True)

    task: Task
    steps: list[StepRecord]
    observations: list[Observation]
    result: ToolResult | None = None
