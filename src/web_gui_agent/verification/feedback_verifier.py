"""Verification for explicit page-level error feedback."""

from web_gui_agent.domain.observation import Observation


class FeedbackVerifier:
    def verify(self, after: Observation) -> tuple[bool, dict[str, bool]]:
        return not after.page_signals.has_error, {"has_error": after.page_signals.has_error}
