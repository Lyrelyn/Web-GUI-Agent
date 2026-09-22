"""Minimal browser-session contract for future execution phases."""

from typing import NewType, Protocol

TabId = NewType("TabId", str)


class BrowserSession(Protocol):
    async def create_tab(self, url: str | None = None) -> TabId: ...

    async def close(self) -> None: ...
