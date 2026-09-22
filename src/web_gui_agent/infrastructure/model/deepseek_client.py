"""DeepSeek's OpenAI-compatible model adapter."""

from typing import Any

from pydantic import TypeAdapter, ValidationError

from web_gui_agent.config.settings import Settings
from web_gui_agent.domain.action import Action
from web_gui_agent.domain.errors import AgentError, DomainError, ErrorCode
from web_gui_agent.domain.observation import Observation
from web_gui_agent.domain.run import SharedMemory, StepRecord
from web_gui_agent.domain.task import TaskInput

_ACTION_ADAPTER: TypeAdapter[Action] = TypeAdapter(Action)


class DeepSeekModelClient:
    """Plans one typed browser action using DeepSeek's compatible endpoint."""

    def __init__(self, *, api_key: str, model: str, client: Any) -> None:
        self._api_key = api_key
        self._model = model
        self._client = client

    @classmethod
    def from_settings(cls, settings: Settings) -> "DeepSeekModelClient":
        if settings.deepseek_api_key is None:
            raise DomainError(
                AgentError(
                    code=ErrorCode.MODEL_INVALID_ACTION,
                    message="DeepSeek API key is not configured.",
                )
            )
        from openai import AsyncOpenAI

        return cls(
            api_key=settings.deepseek_api_key,
            model=settings.deepseek_model,
            client=AsyncOpenAI(
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
            ),
        )

    async def plan(
        self,
        *,
        task: TaskInput,
        observation: Observation,
        memory: SharedMemory,
        history: list[StepRecord],
    ) -> Action:
        _ = memory, history
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Return exactly one JSON object matching the typed browser "
                            "Action schema. Never claim completion without "
                            "FinishAction.expected_text that appears on the page."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Instruction: {task.instruction}\n"
                            f"URL: {observation.url}\n"
                            f"Title: {observation.title}\n"
                            f"Visible text: {observation.text_summary}\n"
                            f"Elements: {observation.elements!r}"
                        ),
                    },
                ],
            )
            content = response.choices[0].message.content
            if not isinstance(content, str):
                raise ValueError("Model response did not contain action JSON.")
            return _ACTION_ADAPTER.validate_json(content)
        except (IndexError, AttributeError, TypeError, ValueError, ValidationError) as exc:
            raise DomainError(
                AgentError(
                    code=ErrorCode.MODEL_INVALID_ACTION,
                    message="DeepSeek returned an invalid action.",
                    retryable=True,
                )
            ) from exc
