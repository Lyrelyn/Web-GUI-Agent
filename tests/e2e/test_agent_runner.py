import asyncio
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from web_gui_agent.application.agent_runner import AgentRunner
from web_gui_agent.browser.playwright_session import PlaywrightBrowserRunFactory
from web_gui_agent.domain.action import (
    Action,
    ClickAction,
    ElementRef,
    ExtractAction,
    FillAction,
    FinishAction,
    LocatorHint,
    NavigateAction,
    SelectAction,
)
from web_gui_agent.domain.task import Task, TaskInput, TaskStatus
from web_gui_agent.infrastructure.clock import SystemClock
from web_gui_agent.infrastructure.persistence.in_memory_task_repository import (
    InMemoryTaskRepository,
)


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return None


@contextmanager
def controlled_server(root: Path) -> Generator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(root)))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join()


class SequenceModel:
    def __init__(self, actions: list[Action]) -> None:
        self._actions = actions

    async def plan(self, **_: object) -> Action:
        return self._actions.pop(0)


def _element(element_id: str) -> ElementRef:
    return ElementRef(
        element_id=element_id,
        locator_hints=[LocatorHint(strategy="test_id", value=element_id)],
    )


async def test_runner_verifies_a_real_controlled_query_flow() -> None:
    fixture_root = Path(__file__).parents[1] / "fixtures" / "web_app"
    repository = InMemoryTaskRepository()
    factory = PlaywrightBrowserRunFactory(timeout_ms=5_000)
    try:
        with controlled_server(fixture_root) as base_url:
            url = f"{base_url}/query.html"
            task = Task.queued(TaskInput(instruction="Search codex"), now=datetime.now(UTC))
            await repository.create(task)
            runner = AgentRunner(
                repository,
                SystemClock(),
                SequenceModel(
                    [
                        NavigateAction(kind="navigate", url=url),
                        FillAction(kind="fill", element=_element("query"), value="codex"),
                        SelectAction(kind="select", element=_element("sort"), value="newest"),
                        ClickAction(kind="click", element=_element("submit")),
                        ExtractAction(kind="extract", element=_element("result")),
                        FinishAction(
                            kind="finish",
                            summary="Result extracted",
                            expected_text="Result: codex (newest)",
                        ),
                    ]
                ),
                factory,
            )

            outcome = await runner.run(task.id, asyncio.Event())

        assert outcome.task.status is TaskStatus.SUCCEEDED
        assert [step.verification.passed for step in outcome.steps if step.verification] == [
            True,
            True,
            True,
            True,
            True,
            True,
        ]
        assert outcome.result is not None
        assert outcome.result.summary == "Result extracted"
    finally:
        await factory.close()
