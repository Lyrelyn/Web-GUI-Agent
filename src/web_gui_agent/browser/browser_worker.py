"""Safe atomic Playwright operations."""

from typing import Any

from playwright.async_api import Error, Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from web_gui_agent.browser.locator_resolver import LocatorResolutionError, LocatorResolver
from web_gui_agent.domain.action import ElementRef, ToolResult
from web_gui_agent.domain.errors import AgentError, ErrorCode


class BrowserWorker:
    def __init__(self, page: Page, timeout_ms: int = 10_000) -> None:
        self._page = page
        self._timeout_ms = timeout_ms
        self._resolver = LocatorResolver()

    async def navigate(self, url: str) -> ToolResult:
        try:
            await self._page.goto(url, wait_until="domcontentloaded", timeout=self._timeout_ms)
            return ToolResult(ok=True, summary="Navigated.")
        except PlaywrightTimeoutError:
            return self._error(ErrorCode.ACTION_TIMEOUT, "Navigation timed out.")
        except Error:
            return self._error(ErrorCode.BROWSER_CRASHED, "Browser navigation failed.")

    async def click(self, element: ElementRef) -> ToolResult:
        return await self._locator_call(element, "click")

    async def fill(self, element: ElementRef, value: str) -> ToolResult:
        return await self._locator_call(element, "fill", value)

    async def select(self, element: ElementRef, value: str) -> ToolResult:
        return await self._locator_call(element, "select_option", value)

    async def extract(self, element: ElementRef, attribute: str | None) -> ToolResult:
        try:
            locator = await self._resolver.resolve(self._page, element)
            data = await (locator.get_attribute(attribute) if attribute else locator.inner_text())
            return ToolResult(ok=True, summary=f"Extracted {element.element_id}.", data=data)
        except LocatorResolutionError:
            return self._error(ErrorCode.LOCATOR_NOT_FOUND, "Element was not found.")
        except PlaywrightTimeoutError:
            return self._error(ErrorCode.ACTION_TIMEOUT, "Extraction timed out.")
        except Error:
            return self._error(ErrorCode.BROWSER_CRASHED, "Browser extraction failed.")

    async def scroll(self, delta_y: int) -> ToolResult:
        try:
            await self._page.mouse.wheel(0, delta_y)
            return ToolResult(ok=True, summary="Scrolled.")
        except Error:
            return self._error(ErrorCode.BROWSER_CRASHED, "Browser scroll failed.")

    async def _locator_call(
        self, element: ElementRef, method: str, value: str | None = None
    ) -> ToolResult:
        try:
            locator = await self._resolver.resolve(self._page, element)
            operation: Any = getattr(locator, method)
            if value is None:
                await operation(timeout=self._timeout_ms)
            else:
                await operation(value, timeout=self._timeout_ms)
            return ToolResult(ok=True, summary=f"Completed {method} on {element.element_id}.")
        except LocatorResolutionError:
            return self._error(ErrorCode.LOCATOR_NOT_FOUND, "Element was not found.")
        except PlaywrightTimeoutError:
            return self._error(ErrorCode.ACTION_TIMEOUT, "Browser operation timed out.")
        except Error:
            return self._error(ErrorCode.BROWSER_CRASHED, "Browser operation failed.")

    @staticmethod
    def _error(code: ErrorCode, message: str) -> ToolResult:
        return ToolResult(ok=False, summary=message, error=AgentError(code=code, message=message))
