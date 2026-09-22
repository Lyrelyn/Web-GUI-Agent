"""The one place that selects concrete infrastructure implementations."""

from web_gui_agent.application.task_service import TaskService
from web_gui_agent.config.settings import Settings
from web_gui_agent.domain.ports.model_client import ModelClient
from web_gui_agent.infrastructure.clock import SystemClock
from web_gui_agent.infrastructure.model.deepseek_client import DeepSeekModelClient
from web_gui_agent.infrastructure.persistence.in_memory_task_repository import (
    InMemoryTaskRepository,
)


def build_task_service(settings: Settings) -> TaskService:
    return TaskService(
        repository=InMemoryTaskRepository(),
        clock=SystemClock(),
        settings=settings,
    )


def build_model_client(settings: Settings) -> ModelClient:
    """Build the real provider lazily when a browser-runner is assembled."""
    return DeepSeekModelClient.from_settings(settings)
