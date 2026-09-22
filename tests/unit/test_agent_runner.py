import asyncio
from datetime import UTC, datetime

import pytest

from web_gui_agent.domain.action import Action, FinishAction, NavigateAction, ToolResult
from web_gui_agent.domain.errors import AgentError, DomainError, ErrorCode
from web_gui_agent.domain.observation import Observation, Viewport
from web_gui_agent.domain.ports.browser_run import BrowserRun
from web_gui_agent.domain.task import Task, TaskInput, TaskStatus
from web_gui_agent.infrastructure.clock import SystemClock
from web_gui_agent.infrastructure.persistence.in_memory_task_repository import (
    InMemoryTaskRepository,
)


class FakeModel:
    def __init__(self, actions: list[Action]) -> None:
        self._actions = actions

    async def plan(self, **_: object) -> Action:
        return self._actions.pop(0)


class FakeRun:
    def __init__(self, result: ToolResult | None = None) -> None:
        self.closed = False
        self._result = result

    async def observe(self) -> Observation:
        return Observation(
            url="http://controlled.test/",
            title="Controlled",
            viewport=Viewport(width=1280, height=720, scroll_y=0),
            text_summary="controlled page",
            captured_at=datetime.now(UTC),
        )

    async def execute(self, action: Action) -> ToolResult:
        _ = action
        return self._result or ToolResult(ok=True, summary="ok")

    async def close(self) -> None:
        self.closed = True


class FakeFactory:
    def __init__(self, run: FakeRun) -> None:
        self.run = run

    async def open(self) -> BrowserRun:
        return self.run


async def test_runner_finishes_task_and_closes_its_browser_run() -> None:
    from web_gui_agent.application.agent_runner import AgentRunner

    repository = InMemoryTaskRepository()
    task = Task.queued(TaskInput(instruction="Finish"), now=datetime.now(UTC))
    await repository.create(task)
    run = FakeRun()
    runner = AgentRunner(
        repository,
        SystemClock(),
        FakeModel([FinishAction(kind="finish", summary="done")]),
        FakeFactory(run),
    )

    outcome = await runner.run(task.id, asyncio.Event())

    assert outcome.task.status is TaskStatus.SUCCEEDED
    assert outcome.steps[-1].action is not None
    assert outcome.steps[-1].action.kind == "finish"
    assert run.closed is True


async def test_runner_marks_task_failed_and_closes_run_on_tool_error() -> None:
    from web_gui_agent.application.agent_runner import AgentRunner

    repository = InMemoryTaskRepository()
    task = Task.queued(TaskInput(instruction="Fail"), now=datetime.now(UTC))
    await repository.create(task)
    run = FakeRun(
        ToolResult(
            ok=False,
            summary="failed",
            error=AgentError(code=ErrorCode.LOCATOR_NOT_FOUND, message="missing"),
        )
    )
    runner = AgentRunner(
        repository,
        SystemClock(),
        FakeModel([NavigateAction(kind="navigate", url="http://controlled.test/")]),
        FakeFactory(run),
    )

    with pytest.raises(DomainError):
        await runner.run(task.id, asyncio.Event())

    failed_task = await repository.get(task.id)
    assert failed_task is not None
    assert failed_task.status is TaskStatus.FAILED
    assert run.closed is True
