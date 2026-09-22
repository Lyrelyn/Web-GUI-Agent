from datetime import UTC, datetime

import pytest

from web_gui_agent.application.task_service import TaskService
from web_gui_agent.config.settings import Settings
from web_gui_agent.domain.task import TaskInput, TaskStatus
from web_gui_agent.infrastructure.persistence.in_memory_task_repository import (
    InMemoryTaskRepository,
)


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 9, 22, tzinfo=UTC)


@pytest.mark.asyncio
async def test_service_applies_configured_defaults_when_options_are_omitted() -> None:
    service = TaskService(
        repository=InMemoryTaskRepository(),
        clock=FixedClock(),
        settings=Settings(default_timeout_ms=30_000, default_max_retries=4),
    )

    task = await service.create(TaskInput(instruction="Find an item"))

    assert task.status is TaskStatus.QUEUED
    assert task.input.options.timeout_ms == 30_000
    assert task.input.options.max_retries == 4
