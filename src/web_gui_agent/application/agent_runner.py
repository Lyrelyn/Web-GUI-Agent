"""Minimal single-page Observe → Plan → Execute state machine."""

import asyncio
from time import perf_counter

from web_gui_agent.domain.action import Action, FinishAction, ToolResult
from web_gui_agent.domain.errors import AgentError, DomainError, ErrorCode, TaskNotFoundError
from web_gui_agent.domain.observation import Observation
from web_gui_agent.domain.ports.browser_run import BrowserRunFactory
from web_gui_agent.domain.ports.clock import Clock
from web_gui_agent.domain.ports.model_client import ModelClient
from web_gui_agent.domain.ports.task_repository import TaskRepository
from web_gui_agent.domain.run import RunOutcome, RunPhase, StepRecord
from web_gui_agent.domain.task import Task, TaskStatus


class AgentRunner:
    """Runs one task using injected browser and model ports."""

    def __init__(
        self,
        repository: TaskRepository,
        clock: Clock,
        model: ModelClient,
        browser_runs: BrowserRunFactory,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._model = model
        self._browser_runs = browser_runs

    async def run(self, task_id: str, cancel_event: asyncio.Event) -> RunOutcome:
        task = await self._get_task(task_id)
        running = task.transition_to(TaskStatus.RUNNING, now=self._clock.now())
        await self._repository.update(running, expected_version=task.version)
        browser_run = await self._browser_runs.open()
        steps: list[StepRecord] = []
        observations: list[Observation] = []
        last_result: ToolResult | None = None
        try:
            while True:
                if cancel_event.is_set():
                    raise DomainError(
                        AgentError(code=ErrorCode.TASK_CANCELLED, message="Task was cancelled.")
                    )
                started = perf_counter()
                observation = await browser_run.observe()
                observations.append(observation)
                action = await self._model.plan(
                    task=running.input, observation=observation, memory={}, history=steps
                )
                if isinstance(action, FinishAction):
                    last_result = ToolResult(ok=True, summary=action.summary)
                    steps.append(self._step(len(steps), action, last_result, observation, started))
                    succeeded = running.transition_to(TaskStatus.SUCCEEDED, now=self._clock.now())
                    await self._repository.update(succeeded, expected_version=running.version)
                    return RunOutcome(
                        task=succeeded,
                        steps=steps,
                        observations=observations,
                        result=last_result,
                    )
                last_result = await browser_run.execute(action)
                steps.append(self._step(len(steps), action, last_result, observation, started))
                if not last_result.ok:
                    raise DomainError(last_result.error or self._browser_error())
        except DomainError:
            failed = running.transition_to(TaskStatus.FAILED, now=self._clock.now())
            await self._repository.update(failed, expected_version=running.version)
            raise
        finally:
            await browser_run.close()

    async def _get_task(self, task_id: str) -> Task:
        task = await self._repository.get(task_id)
        if task is None:
            raise TaskNotFoundError(task_id)
        return task

    @staticmethod
    def _step(
        index: int,
        action: Action,
        result: ToolResult,
        observation: Observation,
        started: float,
    ) -> StepRecord:
        return StepRecord(
            index=index,
            phase=RunPhase.EXECUTE,
            action=action,
            tool_result=result,
            observation=observation,
            duration_ms=int((perf_counter() - started) * 1000),
        )

    @staticmethod
    def _browser_error() -> AgentError:
        return AgentError(code=ErrorCode.BROWSER_CRASHED, message="Browser operation failed.")
