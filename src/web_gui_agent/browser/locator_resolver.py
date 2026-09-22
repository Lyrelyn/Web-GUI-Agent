"""Resolve model-provided locator hints without coordinate-based actions."""

from typing import Any, cast

from playwright.async_api import Locator, Page

from web_gui_agent.domain.action import ElementRef, LocatorHint


class LocatorResolutionError(Exception):
    """No locator hint resolved to exactly one element."""

    def __init__(self, element_id: str) -> None:
        super().__init__(f"Element '{element_id}' could not be resolved.")
        self.element_id = element_id


_PRIORITY = {"test_id": 0, "label": 1, "role": 2, "text": 3, "css": 4}


class LocatorResolver:
    """Resolves the most stable unambiguous hint first."""

    async def resolve(self, page: Page, element: ElementRef) -> Locator:
        hints = sorted(element.locator_hints, key=lambda hint: _PRIORITY[hint.strategy])
        for hint in hints:
            locator = self._from_hint(page, hint)
            if await locator.count() == 1:
                return locator
        raise LocatorResolutionError(element.element_id)

    def _from_hint(self, page: Page, hint: LocatorHint) -> Locator:
        match hint.strategy:
            case "test_id":
                return page.get_by_test_id(hint.value)
            case "label":
                return page.get_by_label(hint.value, exact=True)
            case "role":
                return page.get_by_role(cast(Any, hint.value))
            case "text":
                return page.get_by_text(hint.value, exact=True)
            case "css":
                return page.locator(hint.value)
