"""Verification for navigation effects."""

from web_gui_agent.domain.action import NavigateAction
from web_gui_agent.domain.observation import Observation


class UrlVerifier:
    def verify(self, action: NavigateAction, after: Observation) -> tuple[bool, dict[str, str]]:
        return after.url == action.url, {"url": after.url, "expected_url": action.url}
