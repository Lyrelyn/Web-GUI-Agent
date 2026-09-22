"""Planning interface; concrete model SDKs belong in infrastructure."""

from typing import Protocol

from web_gui_agent.domain.action import Action
from web_gui_agent.domain.observation import Observation
from web_gui_agent.domain.run import SharedMemory, StepRecord
from web_gui_agent.domain.task import TaskInput


class ModelClient(Protocol):
    async def plan(
        self,
        *,
        task: TaskInput,
        observation: Observation,
        memory: SharedMemory,
        history: list[StepRecord],
    ) -> Action: ...
