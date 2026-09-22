"""Playwright implementation of a task-isolated browser run."""

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from web_gui_agent.browser.browser_worker import BrowserWorker
from web_gui_agent.browser.observation_builder import ObservationBuilder
from web_gui_agent.domain.action import Action, ToolResult
from web_gui_agent.domain.observation import Observation
from web_gui_agent.tools.tool_registry import ToolRegistry


class PlaywrightBrowserRun:
    def __init__(self, context: BrowserContext, page: Page, timeout_ms: int) -> None:
        self.context = context
        self._page = page
        self._closed = False
        self._observer = ObservationBuilder()
        self._tools = ToolRegistry(BrowserWorker(page, timeout_ms))

    async def observe(self) -> Observation:
        return await self._observer.build(self._page)

    async def execute(self, action: Action) -> ToolResult:
        return await self._tools.execute(action)

    async def close(self) -> None:
        if not self._closed:
            self._closed = True
            await self.context.close()


class PlaywrightBrowserRunFactory:
    def __init__(self, timeout_ms: int = 10_000) -> None:
        self._timeout_ms = timeout_ms
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None

    async def open(self) -> PlaywrightBrowserRun:
        if self._browser is None:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch()
        context = await self._browser.new_context()
        page = await context.new_page()
        return PlaywrightBrowserRun(context, page, self._timeout_ms)

    async def close(self) -> None:
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None
