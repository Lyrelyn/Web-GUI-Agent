"""Task lifecycle use case. It deliberately does not operate a browser."""

from web_gui_agent.config.settings import Settings
from web_gui_agent.domain.errors import TaskNotFoundError
from web_gui_agent.domain.ports.clock import Clock
from web_gui_agent.domain.ports.task_repository import TaskRepository
from web_gui_agent.domain.task import Task, TaskInput, TaskOptions, TaskStatus


class TaskService:
    def __init__(
        self,
        repository: TaskRepository,
        clock: Clock,
        settings: Settings,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._settings = settings

    async def create(self, task_input: TaskInput) -> Task:
        normalized_input = self._apply_default_options(task_input)
        task = Task.queued(normalized_input, now=self._clock.now())
        return await self._repository.create(task)

    async def get(self, task_id: str) -> Task:
        task = await self._repository.get(task_id)
        if task is None:
            raise TaskNotFoundError(task_id)
        return task

    async def cancel(self, task_id: str) -> Task:
        task = await self.get(task_id)
        cancelled = task.transition_to(TaskStatus.CANCELLED, now=self._clock.now())
        return await self._repository.update(cancelled, expected_version=task.version)

    def _apply_default_options(self, task_input: TaskInput) -> TaskInput:
        if "options" in task_input.model_fields_set:
            return task_input
        return task_input.model_copy(
            update={
                "options": TaskOptions(
                    timeout_ms=self._settings.default_timeout_ms,
                    max_retries=self._settings.default_max_retries,
                )
            }
        )
