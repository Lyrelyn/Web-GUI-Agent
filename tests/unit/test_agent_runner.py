import asyncio
from datetime import UTC, datetime

import pytest

from web_gui_agent.domain.action import Action, FinishAction, NavigateAction, ToolResult
from web_gui_agent.domain.errors import AgentError, DomainError, ErrorCode
from web_gui_agent.domain.observation import Observation, Viewport
from web_gui_agent.domain.ports.browser_run import BrowserRun
from web_gui_agent.domain.task import Task, TaskInput, TaskOptions, TaskStatus
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


class RetryingRun(FakeRun):
    def __init__(self) -> None:
        super().__init__()
        self._results = [
            ToolResult(
                ok=False,
                summary="missing",
                error=AgentError(
                    code=ErrorCode.LOCATOR_NOT_FOUND,
                    message="missing",
                    retryable=True,
                ),
            ),
            ToolResult(ok=True, summary="Navigated."),
        ]
        self.executions = 0

    async def observe(self) -> Observation:
        if self.executions >= 2:
            return Observation(
                url="http://controlled.test/results",
                title="Controlled",
                viewport=Viewport(width=1280, height=720, scroll_y=0),
                text_summary="Result: codex",
                captured_at=datetime.now(UTC),
            )
        return await super().observe()

    async def execute(self, action: Action) -> ToolResult:
        _ = action
        self.executions += 1
        return self._results.pop(0)


class CancelingModel(FakeModel):
    def __init__(self, event: asyncio.Event) -> None:
        super().__init__([NavigateAction(kind="navigate", url="http://controlled.test/")])
        self._event = event

    async def plan(self, **_: object) -> Action:
        self._event.set()
        return await super().plan()


class BrokenFactory:
    async def open(self) -> BrowserRun:
        raise RuntimeError("browser unavailable")


class SlowModel(FakeModel):
    async def plan(self, **_: object) -> Action:
        await asyncio.sleep(1.1)
        return await super().plan()


async def test_runner_finishes_task_and_closes_its_browser_run() -> None:
    from web_gui_agent.application.agent_runner import AgentRunner

    repository = InMemoryTaskRepository()
    task = Task.queued(TaskInput(instruction="Finish"), now=datetime.now(UTC))
    await repository.create(task)
    run = FakeRun()
    runner = AgentRunner(
        repository,
        SystemClock(),
        FakeModel([FinishAction(kind="finish", summary="done", expected_text="controlled page")]),
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


async def test_runner_replans_after_retryable_locator_error() -> None:
    from web_gui_agent.application.agent_runner import AgentRunner

    repository = InMemoryTaskRepository()
    task = Task.queued(
        TaskInput(instruction="Search", options=TaskOptions(max_retries=1)),
        now=datetime.now(UTC),
    )
    await repository.create(task)
    run = RetryingRun()
    runner = AgentRunner(
        repository,
        SystemClock(),
        FakeModel(
            [
                NavigateAction(kind="navigate", url="http://controlled.test/results"),
                NavigateAction(kind="navigate", url="http://controlled.test/results"),
                FinishAction(kind="finish", summary="done", expected_text="Result: codex"),
            ]
        ),
        FakeFactory(run),
    )

    outcome = await runner.run(task.id, asyncio.Event())

    assert outcome.task.status is TaskStatus.SUCCEEDED
    assert run.executions == 2
    assert outcome.steps[0].tool_result is not None
    assert outcome.steps[0].tool_result.ok is False


async def test_runner_cancels_before_dispatching_planned_action() -> None:
    from web_gui_agent.application.agent_runner import AgentRunner

    repository = InMemoryTaskRepository()
    task = Task.queued(TaskInput(instruction="Cancel"), now=datetime.now(UTC))
    await repository.create(task)
    run = FakeRun()
    cancellation = asyncio.Event()
    runner = AgentRunner(
        repository,
        SystemClock(),
        CancelingModel(cancellation),
        FakeFactory(run),
    )

    with pytest.raises(DomainError) as raised:
        await runner.run(task.id, cancellation)

    cancelled_task = await repository.get(task.id)
    assert raised.value.error.code is ErrorCode.TASK_CANCELLED
    assert cancelled_task is not None
    assert cancelled_task.status is TaskStatus.CANCELLED
    assert run.closed is True


async def test_runner_marks_browser_open_failure_as_failed() -> None:
    from web_gui_agent.application.agent_runner import AgentRunner

    repository = InMemoryTaskRepository()
    task = Task.queued(TaskInput(instruction="Open"), now=datetime.now(UTC))
    await repository.create(task)
    runner = AgentRunner(
        repository,
        SystemClock(),
        FakeModel([]),
        BrokenFactory(),
    )

    with pytest.raises(DomainError) as raised:
        await runner.run(task.id, asyncio.Event())

    failed_task = await repository.get(task.id)
    assert raised.value.error.code is ErrorCode.BROWSER_CRASHED
    assert failed_task is not None
    assert failed_task.status is TaskStatus.FAILED


async def test_runner_marks_deadline_expiry_as_action_timeout() -> None:
    from web_gui_agent.application.agent_runner import AgentRunner

    repository = InMemoryTaskRepository()
    task = Task.queued(
        TaskInput(instruction="Timeout", options=TaskOptions(timeout_ms=1_000)),
        now=datetime.now(UTC),
    )
    await repository.create(task)
    run = FakeRun()
    runner = AgentRunner(
        repository,
        SystemClock(),
        SlowModel([FinishAction(kind="finish", summary="done", expected_text="controlled page")]),
        FakeFactory(run),
    )

    with pytest.raises(DomainError) as raised:
        await runner.run(task.id, asyncio.Event())

    failed_task = await repository.get(task.id)
    assert raised.value.error.code is ErrorCode.ACTION_TIMEOUT
    assert failed_task is not None
    assert failed_task.status is TaskStatus.FAILED
    assert run.closed is True
