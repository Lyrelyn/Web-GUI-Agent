import pytest


class FakeBodyLocator:
    async def evaluate(self, _: str) -> dict[str, object]:
        return {
            "elements": [
                {
                    "element_id": "query",
                    "role": None,
                    "name": "codex",
                    "kind": "input",
                    "visible": True,
                    "enabled": True,
                    "value": "codex",
                    "locator_hints": [{"strategy": "test_id", "value": "query"}],
                },
                {
                    "element_id": "secret",
                    "role": None,
                    "name": "",
                    "kind": "input",
                    "visible": True,
                    "enabled": True,
                    "value": None,
                    "locator_hints": [{"strategy": "test_id", "value": "secret"}],
                },
            ],
            "text": "Search\nError: invalid query",
            "viewport": {"width": 1280, "height": 720, "scroll_y": 0},
            "signals": {"has_error": True},
        }


class FakePage:
    def locator(self, selector: str) -> FakeBodyLocator:
        assert selector == "body"
        return FakeBodyLocator()

    async def title(self) -> str:
        return "Controlled"

    url = "http://controlled.test/"


@pytest.mark.asyncio
async def test_observation_builder_keeps_safe_form_values_and_page_error_signal() -> None:
    from web_gui_agent.browser.observation_builder import ObservationBuilder

    observation = await ObservationBuilder().build(FakePage())  # type: ignore[arg-type]

    assert observation.elements[0].value == "codex"
    assert observation.elements[1].value is None
    assert observation.page_signals.has_error is True
