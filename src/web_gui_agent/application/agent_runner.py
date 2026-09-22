"""Minimal single-page Observe → Plan → Execute state machine."""

import asyncio
from time import perf_counter

from web_gui_agent.application.retry_policy import RetryPolicy
from web_gui_agent.domain.action import Action, FinishAction, ToolResult, VerificationResult
from web_gui_agent.domain.errors import AgentError, DomainError, ErrorCode, TaskNotFoundError
from web_gui_agent.domain.observation import Observation
from web_gui_agent.domain.ports.browser_run import BrowserRunFactory
from web_gui_agent.domain.ports.clock import Clock
from web_gui_agent.domain.ports.model_client import ModelClient
from web_gui_agent.domain.ports.task_repository import TaskRepository
from web_gui_agent.domain.run import RunOutcome, RunPhase, StepRecord
from web_gui_agent.domain.task import Task, TaskStatus
from web_gui_agent.verification.action_verifier import ActionVerifier


class AgentRunner:
    """Runs one task using injected browser and model ports."""

    def __init__(
        self,
        repository: TaskRepository,
        clock: Clock,
        model: ModelClient,
        browser_runs: BrowserRunFactory,
        verifier: ActionVerifier | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._model = model
        self._browser_runs = browser_runs
        self._verifier = verifier or ActionVerifier()
        self._retry_policy = retry_policy or RetryPolicy()

    async def run(self, task_id: str, cancel_event: asyncio.Event) -> RunOutcome:
        task = await self._get_task(task_id)
        running = task.transition_to(TaskStatus.RUNNING, now=self._clock.now())
        await self._repository.update(running, expected_version=task.version)
        steps: list[StepRecord] = []
        observations: list[Observation] = []
        last_result: ToolResult | None = None
        browser_run = None
        try:
            async with asyncio.timeout(running.input.options.timeout_ms / 1000):
                browser_run = await self._browser_runs.open()
                attempts = 0
                while True:
                    self._raise_if_cancelled(cancel_event)
                    before = await browser_run.observe()
                    observations.append(before)
                    action = await self._model.plan(
                        task=running.input, observation=before, memory={}, history=steps
                    )
                    self._raise_if_cancelled(cancel_event)
                    started = perf_counter()
                    last_result = (
                        ToolResult(ok=True, summary=action.summary)
                        if isinstance(action, FinishAction)
                        else await browser_run.execute(action)
                    )
                    after = await browser_run.observe()
                    observations.append(after)
                    verification = self._verifier.verify(before, action, last_result, after)
                    error = self._error_for(last_result, verification)
                    steps.append(
                        self._step(
                            len(steps), action, last_result, before, verification, error, started
                        )
                    )
                    if error is not None:
                        if self._retry_policy.should_retry(
                            error, attempt=attempts, max_retries=running.input.options.max_retries
                        ):
                            attempts += 1
                            continue
                        raise DomainError(error)
                    attempts = 0
                    if isinstance(action, FinishAction):
                        succeeded = await self._terminalize(running, TaskStatus.SUCCEEDED)
                        return RunOutcome(
                            task=succeeded,
                            steps=steps,
                            observations=observations,
                            result=last_result,
                        )
        except TimeoutError as exc:
            error = AgentError(
                code=ErrorCode.ACTION_TIMEOUT,
                message="Task timed out.",
                retryable=False,
            )
            await self._terminalize(running, TaskStatus.FAILED)
            raise DomainError(error) from exc
        except DomainError as exc:
            terminal = (
                TaskStatus.CANCELLED
                if exc.error.code is ErrorCode.TASK_CANCELLED
                else TaskStatus.NEEDS_CONFIRMATION
                if exc.error.code is ErrorCode.POLICY_BLOCKED
                else TaskStatus.FAILED
            )
            await self._terminalize(running, terminal)
            raise
        except Exception as exc:
            error = self._browser_error()
            await self._terminalize(running, TaskStatus.FAILED)
            raise DomainError(error) from exc
        finally:
            if browser_run is not None:
                try:
                    await browser_run.close()
                except Exception:
                    pass

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
        verification: VerificationResult,
        error: AgentError | None,
        started: float,
    ) -> StepRecord:
        return StepRecord(
            index=index,
            phase=RunPhase.VERIFY,
            action=action,
            tool_result=result,
            verification=verification,
            observation=observation,
            duration_ms=int((perf_counter() - started) * 1000),
            error=error,
        )

    async def _terminalize(self, running: Task, target: TaskStatus) -> Task:
        current = await self._repository.get(running.id)
        if current is None:
            raise TaskNotFoundError(running.id)
        if current.status in {
            TaskStatus.SUCCEEDED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
            TaskStatus.NEEDS_CONFIRMATION,
        }:
            return current
        terminal = current.transition_to(target, now=self._clock.now())
        return await self._repository.update(terminal, expected_version=current.version)

    @staticmethod
    def _raise_if_cancelled(cancel_event: asyncio.Event) -> None:
        if cancel_event.is_set():
            raise DomainError(
                AgentError(code=ErrorCode.TASK_CANCELLED, message="Task was cancelled.")
            )

    @staticmethod
    def _error_for(
        result: ToolResult, verification: VerificationResult
    ) -> AgentError | None:
        if not result.ok:
            return result.error or AgentRunner._browser_error()
        if not verification.passed:
            return AgentError(code=ErrorCode.VERIFICATION_FAILED, message=verification.reason)
        return None

    @staticmethod
    def _browser_error() -> AgentError:
        return AgentError(code=ErrorCode.BROWSER_CRASHED, message="Browser operation failed.")
