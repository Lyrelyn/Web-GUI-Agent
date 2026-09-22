"""Verification for values written into form controls."""

from web_gui_agent.domain.action import FillAction, SelectAction
from web_gui_agent.domain.observation import Observation


class FormVerifier:
    def verify(
        self, action: FillAction | SelectAction, after: Observation
    ) -> tuple[bool, dict[str, str | None]]:
        element = next(
            (
                candidate
                for candidate in after.elements
                if candidate.element_id == action.element.element_id
            ),
            None,
        )
        actual = element.value if element is not None else None
        return actual == action.value, {"value": actual, "expected_value": action.value}
