from datetime import UTC, datetime
from typing import cast

import pytest
from pydantic import TypeAdapter

from web_gui_agent.domain.action import Action, ScrollAction, SelectAction
from web_gui_agent.domain.errors import InvalidStateTransitionError
from web_gui_agent.domain.task import Task, TaskInput, TaskStatus


def test_task_starts_queued_and_has_utc_timestamps() -> None:
    now = datetime(2026, 9, 22, tzinfo=UTC)

    task = Task.queued(TaskInput(instruction="Find an item"), now=now)

    assert task.status is TaskStatus.QUEUED
    assert task.created_at == now
    assert task.updated_at == now
    assert task.version == 0


def test_state_transition_is_monotonic() -> None:
    now = datetime(2026, 9, 22, tzinfo=UTC)
    task = Task.queued(TaskInput(instruction="Find an item"), now=now)

    running = task.transition_to(TaskStatus.RUNNING, now=now)
    completed = running.transition_to(TaskStatus.SUCCEEDED, now=now)

    assert running.version == 1
    assert completed.status is TaskStatus.SUCCEEDED
    assert completed.version == 2
    with pytest.raises(InvalidStateTransitionError):
        completed.transition_to(TaskStatus.RUNNING, now=now)


@pytest.mark.parametrize("start_url", ["example.com", "ftp://example.com", "http:///path"])
def test_task_input_rejects_non_http_start_urls(start_url: str) -> None:
    with pytest.raises(ValueError, match="start_url"):
        TaskInput(instruction="Find an item", start_url=start_url)


@pytest.mark.parametrize("instruction", ["", "   "])
def test_task_input_rejects_blank_instruction(instruction: str) -> None:
    with pytest.raises(ValueError):
        TaskInput(instruction=instruction)


def test_action_union_accepts_select_and_scroll_actions() -> None:
    element = {
        "element_id": "sort",
        "locator_hints": [{"strategy": "test_id", "value": "sort"}],
    }

    select = cast(
        Action,
        TypeAdapter(Action).validate_python(
            {"kind": "select", "element": element, "value": "newest"}
        ),
    )
    scroll = cast(Action, TypeAdapter(Action).validate_python({"kind": "scroll", "delta_y": 320}))

    assert isinstance(select, SelectAction)
    assert isinstance(scroll, ScrollAction)
