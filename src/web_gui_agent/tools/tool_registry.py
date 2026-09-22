"""Dispatch typed actions to browser-worker operations."""

from web_gui_agent.browser.browser_worker import BrowserWorker
from web_gui_agent.domain.action import (
    Action,
    ClickAction,
    ExtractAction,
    FillAction,
    NavigateAction,
    ScrollAction,
    SelectAction,
    ToolResult,
)
from web_gui_agent.domain.errors import AgentError, ErrorCode


class ToolRegistry:
    def __init__(self, worker: BrowserWorker) -> None:
        self._worker = worker

    async def execute(self, action: Action) -> ToolResult:
        match action:
            case NavigateAction():
                return await self._worker.navigate(action.url)
            case ClickAction():
                return await self._worker.click(action.element)
            case FillAction():
                return await self._worker.fill(action.element, action.value)
            case SelectAction():
                return await self._worker.select(action.element, action.value)
            case ExtractAction():
                return await self._worker.extract(action.element, action.attribute)
            case ScrollAction():
                return await self._worker.scroll(action.delta_y)
            case _:
                return ToolResult(
                    ok=False,
                    summary="Finish is handled by AgentRunner.",
                    error=AgentError(
                        code=ErrorCode.MODEL_INVALID_ACTION,
                        message="Finish is handled by AgentRunner.",
                    ),
                )
