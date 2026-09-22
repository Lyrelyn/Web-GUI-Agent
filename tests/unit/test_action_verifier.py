from datetime import UTC, datetime

from web_gui_agent.domain.action import (
    ClickAction,
    ElementRef,
    FillAction,
    FinishAction,
    LocatorHint,
    NavigateAction,
    ToolResult,
)
from web_gui_agent.domain.observation import ElementCandidate, Observation, PageSignals, Viewport


def _observation(
    *,
    url: str = "http://controlled.test/",
    text: str = "Initial page",
    elements: list[ElementCandidate] | None = None,
    has_error: bool = False,
) -> Observation:
    return Observation(
        url=url,
        title="Controlled",
        viewport=Viewport(width=1280, height=720, scroll_y=0),
        elements=elements or [],
        text_summary=text,
        page_signals=PageSignals(has_error=has_error),
        captured_at=datetime.now(UTC),
    )


def _element(value: str | None = None) -> ElementCandidate:
    return ElementCandidate(
        element_id="query",
        kind="input",
        visible=True,
        enabled=True,
        value=value,
        locator_hints=[LocatorHint(strategy="test_id", value="query")],
    )


def _ref() -> ElementRef:
    return ElementRef(
        element_id="query",
        locator_hints=[LocatorHint(strategy="test_id", value="query")],
    )


def test_verifier_accepts_navigation_only_when_target_url_was_reached() -> None:
    from web_gui_agent.verification.action_verifier import ActionVerifier

    verification = ActionVerifier().verify(
        _observation(),
        NavigateAction(kind="navigate", url="http://controlled.test/results"),
        ToolResult(ok=True, summary="Navigated."),
        _observation(url="http://controlled.test/results"),
    )

    assert verification.passed is True
    assert verification.evidence["url"] == "http://controlled.test/results"


def test_verifier_accepts_fill_only_when_observation_contains_new_value() -> None:
    from web_gui_agent.verification.action_verifier import ActionVerifier

    verification = ActionVerifier().verify(
        _observation(elements=[_element()]),
        FillAction(kind="fill", element=_ref(), value="codex"),
        ToolResult(ok=True, summary="Filled."),
        _observation(elements=[_element("codex")]),
    )

    assert verification.passed is True
    assert verification.evidence["value"] == "codex"


def test_verifier_accepts_click_when_visible_page_text_changes() -> None:
    from web_gui_agent.verification.action_verifier import ActionVerifier

    verification = ActionVerifier().verify(
        _observation(text="Search"),
        ClickAction(kind="click", element=_ref()),
        ToolResult(ok=True, summary="Clicked."),
        _observation(text="Search\nResult: codex"),
    )

    assert verification.passed is True
    assert verification.evidence["text_changed"] is True


def test_verifier_rejects_action_when_page_reports_an_error() -> None:
    from web_gui_agent.verification.action_verifier import ActionVerifier

    verification = ActionVerifier().verify(
        _observation(),
        ClickAction(kind="click", element=_ref()),
        ToolResult(ok=True, summary="Clicked."),
        _observation(has_error=True),
    )

    assert verification.passed is False
    assert verification.reason == "Page reported an error."


def test_verifier_rejects_finish_when_required_evidence_is_absent() -> None:
    from web_gui_agent.verification.action_verifier import ActionVerifier

    verification = ActionVerifier().verify(
        _observation(text="No completed result"),
        FinishAction(kind="finish", summary="Done", expected_text="Result: codex"),
        ToolResult(ok=True, summary="Done"),
        _observation(text="No completed result"),
    )

    assert verification.passed is False
    assert verification.reason == "Completion evidence was not found."
