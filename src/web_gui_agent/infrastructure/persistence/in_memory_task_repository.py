"""Development-only repository that retains tasks for one process lifetime."""

import asyncio

from web_gui_agent.domain.errors import VersionConflictError
from web_gui_agent.domain.task import Task


class InMemoryTaskRepository:
    """Concurrency-safe task repository with conditional updates."""

    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}
        self._lock = asyncio.Lock()

    async def create(self, task: Task) -> Task:
        async with self._lock:
            self._tasks[task.id] = task
            return task

    async def get(self, task_id: str) -> Task | None:
        async with self._lock:
            return self._tasks.get(task_id)

    async def update(self, task: Task, *, expected_version: int) -> Task:
        async with self._lock:
            current = self._tasks.get(task.id)
            if current is None or current.version != expected_version:
                raise VersionConflictError(task.id)
            self._tasks[task.id] = task
            return task
