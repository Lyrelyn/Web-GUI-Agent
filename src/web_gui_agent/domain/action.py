"""Stable tool-facing action contracts."""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from web_gui_agent.domain.errors import AgentError


class LocatorHint(BaseModel):
    model_config = ConfigDict(frozen=True)

    strategy: Literal["role", "label", "text", "css", "test_id"]
    value: str = Field(min_length=1)


class ElementRef(BaseModel):
    model_config = ConfigDict(frozen=True)

    element_id: str = Field(min_length=1)
    locator_hints: list[LocatorHint] = Field(min_length=1)


class NavigateAction(BaseModel):
    kind: Literal["navigate"]
    url: str


class ClickAction(BaseModel):
    kind: Literal["click"]
    element: ElementRef


class FillAction(BaseModel):
    kind: Literal["fill"]
    element: ElementRef
    value: str


class SelectAction(BaseModel):
    kind: Literal["select"]
    element: ElementRef
    value: str = Field(min_length=1)


class ExtractAction(BaseModel):
    kind: Literal["extract"]
    element: ElementRef
    attribute: str | None = None


class ScrollAction(BaseModel):
    kind: Literal["scroll"]
    delta_y: int


class FinishAction(BaseModel):
    kind: Literal["finish"]
    summary: str = Field(min_length=1)
    expected_text: str | None = Field(default=None, min_length=1)


Action = Annotated[
    NavigateAction
    | ClickAction
    | FillAction
    | SelectAction
    | ExtractAction
    | ScrollAction
    | FinishAction,
    Field(discriminator="kind"),
]


class ToolResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    ok: bool
    summary: str
    data: Any | None = None
    error: AgentError | None = None


class VerificationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    passed: bool
    reason: str
    evidence: dict[str, Any] = Field(default_factory=dict)
