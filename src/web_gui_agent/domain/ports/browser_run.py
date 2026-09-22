"""Application-facing browser execution boundary."""

from typing import Protocol

from web_gui_agent.domain.action import Action, ToolResult
from web_gui_agent.domain.observation import Observation


class BrowserRun(Protocol):
    """One task's isolated browser context."""

    async def observe(self) -> Observation: ...

    async def execute(self, action: Action) -> ToolResult: ...

    async def close(self) -> None: ...


class BrowserRunFactory(Protocol):
    """Creates independent browser contexts for task executions."""

    async def open(self) -> BrowserRun: ...
