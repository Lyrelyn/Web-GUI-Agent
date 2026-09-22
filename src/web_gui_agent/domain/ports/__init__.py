"""Dependency-inversion interfaces used by application services."""

from web_gui_agent.domain.ports.browser_run import BrowserRun, BrowserRunFactory

__all__ = ["BrowserRun", "BrowserRunFactory"]
