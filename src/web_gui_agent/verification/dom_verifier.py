"""Verification for observable DOM changes."""

from web_gui_agent.domain.action import ClickAction, ExtractAction, ScrollAction
from web_gui_agent.domain.observation import Observation


class DomVerifier:
    def verify(
        self,
        before: Observation,
        action: ClickAction | ExtractAction | ScrollAction,
        after: Observation,
    ) -> tuple[bool, dict[str, bool | int]]:
        if isinstance(action, ClickAction):
            changed = before.text_summary != after.text_summary
            return changed, {"text_changed": changed}
        if isinstance(action, ScrollAction):
            changed = before.viewport.scroll_y != after.viewport.scroll_y
            return changed, {"scroll_y": after.viewport.scroll_y}
        return True, {"text_changed": False}
