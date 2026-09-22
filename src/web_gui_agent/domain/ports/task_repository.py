"""Task storage interface with optimistic concurrency."""

from typing import Protocol

from web_gui_agent.domain.task import Task


class TaskRepository(Protocol):
    async def create(self, task: Task) -> Task: ...

    async def get(self, task_id: str) -> Task | None: ...

    async def update(self, task: Task, *, expected_version: int) -> Task: ...
