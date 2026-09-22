"""Model-safe view of a page; browser-specific values are mapped into these types."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from web_gui_agent.domain.action import LocatorHint


def _empty_locator_hints() -> list[LocatorHint]:
    return []


class Viewport(BaseModel):
    model_config = ConfigDict(frozen=True)

    width: int = Field(ge=0)
    height: int = Field(ge=0)
    scroll_y: int = Field(ge=0)


class PageSignals(BaseModel):
    model_config = ConfigDict(frozen=True)

    has_dialog: bool = False
    has_error: bool = False
    is_loading: bool = False


class ElementCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    element_id: str
    role: str | None = None
    name: str | None = None
    kind: Literal["link", "button", "input", "select", "textarea", "text", "other"]
    visible: bool
    enabled: bool | None = None
    locator_hints: list[LocatorHint] = Field(default_factory=_empty_locator_hints)


def _empty_element_candidates() -> list[ElementCandidate]:
    return []


class Observation(BaseModel):
    model_config = ConfigDict(frozen=True)

    url: str
    title: str
    viewport: Viewport
    elements: list[ElementCandidate] = Field(default_factory=_empty_element_candidates)
    text_summary: str
    page_signals: PageSignals = Field(default_factory=PageSignals)
    captured_at: datetime
