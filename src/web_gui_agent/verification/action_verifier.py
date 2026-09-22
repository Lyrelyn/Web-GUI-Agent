"""Aggregate evidence checks for one browser action."""

from collections.abc import Mapping

from web_gui_agent.domain.action import (
    Action,
    ClickAction,
    ExtractAction,
    FillAction,
    NavigateAction,
    ScrollAction,
    SelectAction,
    ToolResult,
    VerificationResult,
)
from web_gui_agent.domain.observation import Observation
from web_gui_agent.verification.dom_verifier import DomVerifier
from web_gui_agent.verification.feedback_verifier import FeedbackVerifier
from web_gui_agent.verification.form_verifier import FormVerifier
from web_gui_agent.verification.url_verifier import UrlVerifier


class ActionVerifier:
    """Checks action effects with page evidence rather than model assertions."""

    def __init__(self) -> None:
        self._url = UrlVerifier()
        self._form = FormVerifier()
        self._dom = DomVerifier()
        self._feedback = FeedbackVerifier()

    def verify(
        self,
        before: Observation,
        action: Action,
        result: ToolResult,
        after: Observation,
    ) -> VerificationResult:
        if not result.ok:
            return VerificationResult(passed=False, reason=result.summary, evidence={})
        feedback_ok, feedback_evidence = self._feedback.verify(after)
        if not feedback_ok:
            return VerificationResult(
                passed=False,
                reason="Page reported an error.",
                evidence=feedback_evidence,
        )
        if isinstance(action, NavigateAction):
            url_passed, url_evidence = self._url.verify(action, after)
            return self._result(url_passed, "Navigation URL did not match.", url_evidence)
        if isinstance(action, FillAction | SelectAction):
            form_passed, form_evidence = self._form.verify(action, after)
            return self._result(form_passed, "Form value did not match.", form_evidence)
        if isinstance(action, ClickAction | ExtractAction | ScrollAction):
            dom_passed, dom_evidence = self._dom.verify(before, action, after)
            return self._result(dom_passed, "Page did not change as expected.", dom_evidence)
        expected = action.expected_text
        passed = expected is not None and expected in after.text_summary
        return self._result(
            passed,
            "Completion evidence was not found.",
            {"expected_text": expected, "text_found": passed},
        )

    @staticmethod
    def _result(
        passed: bool,
        failure_reason: str,
        evidence: Mapping[str, object],
    ) -> VerificationResult:
        return VerificationResult(
            passed=passed,
            reason="Action verified." if passed else failure_reason,
            evidence=dict(evidence),
        )
