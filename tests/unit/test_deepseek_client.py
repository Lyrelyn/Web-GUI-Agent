from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from web_gui_agent.domain.errors import DomainError, ErrorCode
from web_gui_agent.domain.observation import Observation, Viewport
from web_gui_agent.domain.task import TaskInput


class FakeCompletions:
    def __init__(self, content: str) -> None:
        self._content = content

    async def create(self, **_: object) -> object:
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self._content))]
        )


class FakeClient:
    def __init__(self, content: str) -> None:
        self.chat = SimpleNamespace(completions=FakeCompletions(content))


def _observation() -> Observation:
    return Observation(
        url="http://controlled.test/",
        title="Controlled",
        viewport=Viewport(width=1280, height=720, scroll_y=0),
        text_summary="Search page",
        captured_at=datetime.now(UTC),
    )


async def test_deepseek_client_validates_provider_json_as_typed_action() -> None:
    from web_gui_agent.infrastructure.model.deepseek_client import DeepSeekModelClient

    client = DeepSeekModelClient(
        api_key="test-key",
        model="deepseek-chat",
        client=FakeClient('{"kind":"navigate","url":"http://controlled.test/results"}'),
    )

    action = await client.plan(
        task=TaskInput(instruction="Search"), observation=_observation(), memory={}, history=[]
    )

    assert action.kind == "navigate"


async def test_deepseek_client_maps_malformed_provider_action_to_safe_domain_error() -> None:
    from web_gui_agent.infrastructure.model.deepseek_client import DeepSeekModelClient

    client = DeepSeekModelClient(
        api_key="test-key",
        model="deepseek-chat",
        client=FakeClient("not JSON"),
    )

    with pytest.raises(DomainError) as raised:
        await client.plan(
            task=TaskInput(instruction="Search"), observation=_observation(), memory={}, history=[]
        )

    assert raised.value.error.code is ErrorCode.MODEL_INVALID_ACTION
    assert "not JSON" not in raised.value.error.message


def test_settings_exposes_optional_deepseek_configuration() -> None:
    from web_gui_agent.config.settings import Settings

    settings = Settings()

    assert settings.deepseek_api_key is None
    assert settings.deepseek_model == "deepseek-chat"
