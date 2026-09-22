from datetime import UTC, datetime

import pytest

from web_gui_agent.domain.errors import VersionConflictError
from web_gui_agent.domain.task import Task, TaskInput, TaskStatus
from web_gui_agent.infrastructure.persistence.in_memory_task_repository import (
    InMemoryTaskRepository,
)


@pytest.mark.asyncio
async def test_conditional_update_rejects_stale_version() -> None:
    repository = InMemoryTaskRepository()
    now = datetime(2026, 9, 22, tzinfo=UTC)
    task = await repository.create(Task.queued(TaskInput(instruction="Find an item"), now=now))
    running = task.transition_to(TaskStatus.RUNNING, now=now)

    await repository.update(running, expected_version=task.version)

    stale_cancelled = task.transition_to(TaskStatus.CANCELLED, now=now)
    with pytest.raises(VersionConflictError):
        await repository.update(stale_cancelled, expected_version=task.version)


@pytest.mark.asyncio
async def test_get_returns_none_for_unknown_task() -> None:
    repository = InMemoryTaskRepository()

    assert await repository.get("missing") is None
