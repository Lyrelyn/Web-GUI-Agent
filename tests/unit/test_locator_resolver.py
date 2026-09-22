import pytest

from web_gui_agent.domain.action import ElementRef, LocatorHint


class FakeLocator:
    def __init__(self, count: int) -> None:
        self._count = count

    async def count(self) -> int:
        return self._count


class FakePage:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def get_by_test_id(self, value: str) -> FakeLocator:
        self.calls.append(("test_id", value))
        return FakeLocator(1)

    def get_by_text(self, value: str, *, exact: bool = True) -> FakeLocator:
        self.calls.append(("text", value))
        return FakeLocator(1)


@pytest.mark.asyncio
async def test_resolver_uses_test_id_before_text() -> None:
    from web_gui_agent.browser.locator_resolver import LocatorResolver

    page = FakePage()
    element = ElementRef(
        element_id="save",
        locator_hints=[
            LocatorHint(strategy="text", value="Save"),
            LocatorHint(strategy="test_id", value="save"),
        ],
    )

    await LocatorResolver().resolve(page, element)  # type: ignore[arg-type]

    assert page.calls == [("test_id", "save")]
