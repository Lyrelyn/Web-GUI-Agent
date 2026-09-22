# Phase 2 Single-Page Browser Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute a scripted task in an isolated Playwright browser context through an observe-plan-act loop, retaining its semantic observations and step results.

**Architecture:** Keep the application layer dependent on new browser-run and model-client ports. A Playwright adapter owns the browser, context, page, locator resolution, observation building, and safe atomic actions; an injected `AgentRunner` only coordinates task state and records. The tool registry is the sole action dispatcher, and an e2e test drives it with a scripted fake model against a local controlled query page.

**Tech Stack:** Python 3.12+, Pydantic v2, asyncio, Playwright Python, pytest, pytest-asyncio, pytest-playwright, Ruff, mypy strict, Pyright strict.

**Spec:** `设计文档.md` (section 5, 阶段 2：单页浏览器闭环)

## Global Constraints

- The domain package may depend only on Python standard library and Pydantic; it must not import FastAPI, Playwright, database, or model-SDK code.
- A task uses a new isolated Browser Context; all pages, contexts, and the browser runtime must close in `finally`, including when an action fails.
- Browser operations are allowed only through typed `Action` values and the whitelisted tool registry; free model text never reaches Playwright directly.
- Add `playwright` and `pytest-playwright` as bounded development dependencies and document `uv run playwright install chromium` for the local Chromium prerequisite.
- Tests use only a local, controlled fixture site. No external network, credentials, secrets, or production websites are used.
- Preserve the existing Windows/Python 3.12+ target, Ruff 100-column formatting, mypy strict, and Pyright strict configuration.
- Phase 2 deliberately does not add the phase-3 scheduler, verification/retry policy, multi-tab state, model provider, SQLite persistence, screenshots, or Page-Agent bridge.

## Review Focus

- A browser-launch failure must be converted to `BROWSER_CRASHED`, leave the task `FAILED`, and not leak a partially created Playwright runtime.
- A locator whose highest-priority hint matches multiple controls must not silently select an arbitrary destructive control; the resolver should continue only when a hint is unambiguous.
- An invisible, disabled, or script/style DOM node must not appear as a candidate an LLM can target.
- A model action after `finish` must never be requested or executed; the runner must terminate the loop from the returned finish action.
- A task already in a terminal state must not be transitioned or run again; phase-3 scheduling will own duplicate-run coordination.

---

### Task 1: Extend the typed execution contracts and install browser test dependencies

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/web_gui_agent/domain/action.py`
- Modify: `src/web_gui_agent/domain/run.py`
- Create: `src/web_gui_agent/domain/ports/browser_run.py`
- Modify: `src/web_gui_agent/domain/ports/__init__.py`
- Modify: `tests/unit/test_task.py`
- Create: `tests/unit/test_browser_run_contract.py`

**Interfaces:**
- Consumes: existing `Action`, `Observation`, `ToolResult`, `TaskInput`, and `Task` domain contracts.
- Produces: `SelectAction`, `ScrollAction`, `Action` discriminator entries, `RunOutcome`, and `BrowserRunFactory.open() -> BrowserRun` for the later browser adapter and runner.

- [ ] **Step 1: Write failing domain-contract tests**

```python
from web_gui_agent.domain.action import ScrollAction, SelectAction


def test_action_union_accepts_select_and_scroll_actions() -> None:
    select = TypeAdapter(Action).validate_python(
        {"kind": "select", "element": ELEMENT, "value": "newest"}
    )
    scroll = TypeAdapter(Action).validate_python({"kind": "scroll", "delta_y": 320})

    assert isinstance(select, SelectAction)
    assert isinstance(scroll, ScrollAction)
```

```python
class BrowserRun(Protocol):
    async def observe(self) -> Observation: ...
    async def execute(self, action: Action) -> ToolResult: ...
    async def close(self) -> None: ...


class BrowserRunFactory(Protocol):
    async def open(self) -> BrowserRun: ...
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `pytest tests/unit/test_task.py tests/unit/test_browser_run_contract.py -q`

Expected: FAIL because `select`, `scroll`, `RunOutcome`, and browser-run contracts are not yet defined.

- [ ] **Step 3: Implement the smallest contracts and dependencies**

```python
class SelectAction(BaseModel):
    kind: Literal["select"]
    element: ElementRef
    value: str = Field(min_length=1)


class ScrollAction(BaseModel):
    kind: Literal["scroll"]
    delta_y: int
```

```python
class RunOutcome(BaseModel):
    task: Task
    steps: list[StepRecord]
    observations: list[Observation]
    result: ToolResult | None = None
```

Add bounded `playwright` and `pytest-playwright` entries to the `dev` dependency group. Add `SelectAction | ScrollAction` to the existing discriminated `Action` union, and add `observation: Observation | None = None` to `StepRecord` so phase 2 retains compact semantic observations while phase 5 adds durable artifact references.

- [ ] **Step 4: Run the focused tests to verify they pass**

Run: `pytest tests/unit/test_task.py tests/unit/test_browser_run_contract.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the contract change**

```bash
git add pyproject.toml src/web_gui_agent/domain tests/unit/test_task.py tests/unit/test_browser_run_contract.py
git commit -m "feat: add browser execution contracts"
```

### Task 2: Implement isolated Playwright context and deterministic locator resolution

**Files:**
- Create: `src/web_gui_agent/browser/__init__.py`
- Create: `src/web_gui_agent/browser/playwright_session.py`
- Create: `src/web_gui_agent/browser/locator_resolver.py`
- Create: `tests/unit/test_locator_resolver.py`
- Create: `tests/e2e/test_playwright_session.py`

**Interfaces:**
- Consumes: `LocatorHint`, `ElementRef`, `ErrorCode`, and the `BrowserRun` protocol from Task 1.
- Produces: `LocatorResolver.resolve(page, element) -> Locator`, `PlaywrightBrowserRun`, and `PlaywrightBrowserRunFactory.open() -> BrowserRun` for Tasks 3–5.

- [ ] **Step 1: Write failing locator and lifecycle tests**

```python
async def test_resolver_uses_test_id_before_role_and_text(page: Page) -> None:
    await page.set_content('<button>Save</button><button data-testid="save">Store</button>')
    locator = await LocatorResolver().resolve(
        page,
        ElementRef(
            element_id="save",
            locator_hints=[
                LocatorHint(strategy="text", value="Save"),
                LocatorHint(strategy="test_id", value="save"),
            ],
        ),
    )

    await expect(locator).to_have_text("Store")
```

```python
async def test_each_opened_run_uses_a_distinct_context_and_closes_it() -> None:
    factory = PlaywrightBrowserRunFactory()
    first = await factory.open()
    second = await factory.open()

    assert first.context is not second.context
    await first.close()
    await second.close()
    await factory.close()
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `pytest tests/unit/test_locator_resolver.py tests/e2e/test_playwright_session.py -q`

Expected: FAIL because the browser package, resolver, and factory do not exist.

- [ ] **Step 3: Implement stable resolution and resource ownership**

```python
_PRIORITY = {"test_id": 0, "label": 1, "role": 2, "text": 3, "css": 4}

async def resolve(self, page: Page, element: ElementRef) -> Locator:
    for hint in sorted(element.locator_hints, key=lambda item: _PRIORITY[item.strategy]):
        locator = self._from_hint(page, hint)
        if await locator.count() == 1:
            return locator
    raise LocatorResolutionError(element.element_id)
```

`PlaywrightBrowserRunFactory` starts `async_playwright()`, launches Chromium once, and `open()` creates a new context and a run-owned page. `PlaywrightBrowserRun.close()` closes its context idempotently. `factory.close()` closes all still-open contexts, then browser and Playwright runtime idempotently. Translate closed browser/page errors to the stable `BROWSER_CRASHED` error at the adapter boundary.

- [ ] **Step 4: Run the focused tests to verify they pass**

Run: `pytest tests/unit/test_locator_resolver.py tests/e2e/test_playwright_session.py -q`

Expected: PASS after `uv run playwright install chromium` has installed the local browser.

- [ ] **Step 5: Commit the browser lifecycle and resolver**

```bash
git add src/web_gui_agent/browser tests/unit/test_locator_resolver.py tests/e2e/test_playwright_session.py
git commit -m "feat: add isolated playwright browser runs"
```

### Task 3: Build bounded semantic observations from the current page

**Files:**
- Create: `src/web_gui_agent/browser/observation_builder.py`
- Create: `tests/unit/test_observation_builder.py`
- Create: `tests/fixtures/web_app/observation.html`

**Interfaces:**
- Consumes: Playwright `Page`, `ElementCandidate`, `LocatorHint`, `PageSignals`, and `Viewport`.
- Produces: `ObservationBuilder.build(page) -> Observation` for `PlaywrightBrowserRun.observe()` in Task 5.

- [ ] **Step 1: Write failing visibility and candidate-order tests**

```python
async def test_builder_keeps_visible_interactive_nodes_and_excludes_hidden_content(page: Page) -> None:
    await page.goto(controlled_url("observation.html"))

    observation = await ObservationBuilder().build(page)

    assert [candidate.element_id for candidate in observation.elements] == ["search", "submit"]
    assert observation.elements[0].locator_hints[0] == LocatorHint(
        strategy="test_id", value="search"
    )
    assert "private" not in observation.text_summary
```

The fixture contains a visible labelled input and test-id button, an element with `display:none`, a disabled control, and script/style text. The expected candidate list must include only visible enabled interactive controls and task-relevant text.

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `pytest tests/unit/test_observation_builder.py -q`

Expected: FAIL because `ObservationBuilder` does not exist.

- [ ] **Step 3: Implement the minimal DOM-to-domain mapper**

```python
async def build(self, page: Page) -> Observation:
    payload = await page.locator("body").evaluate(_OBSERVATION_SCRIPT)
    return Observation(
        url=page.url,
        title=await page.title(),
        viewport=Viewport(**payload["viewport"]),
        elements=[ElementCandidate.model_validate(item) for item in payload["elements"]],
        text_summary=payload["text_summary"],
        page_signals=PageSignals(**payload["page_signals"]),
        captured_at=self._clock.now(),
    )
```

The page-evaluation script must collect only visible, enabled `a`, `button`, `input`, `select`, and `textarea` nodes; supply candidate ids deterministically (`data-testid` first, then DOM order); and emit locator hints ordered `test_id`, `label`, `role`, `text`, `css`. Limit `text_summary` to visible body text so scripts, styles, and hidden content cannot enter model context.

- [ ] **Step 4: Run the focused test to verify it passes**

Run: `pytest tests/unit/test_observation_builder.py -q`

Expected: PASS.

- [ ] **Step 5: Commit observation construction**

```bash
git add src/web_gui_agent/browser/observation_builder.py tests/unit/test_observation_builder.py tests/fixtures/web_app/observation.html
git commit -m "feat: build visible page observations"
```

### Task 4: Add safe browser worker operations and whitelist their dispatch

**Files:**
- Create: `src/web_gui_agent/browser/browser_worker.py`
- Create: `src/web_gui_agent/tools/__init__.py`
- Create: `src/web_gui_agent/tools/tool_registry.py`
- Create: `tests/e2e/test_browser_worker.py`
- Create: `tests/unit/test_tool_registry.py`

**Interfaces:**
- Consumes: `Page`, `LocatorResolver`, all `Action` variants, and `ToolResult`.
- Produces: `BrowserWorker.navigate/click/fill/select/extract/scroll`, `ToolRegistry.execute(action) -> ToolResult`, and typed `LOCATOR_NOT_FOUND`, `ACTION_TIMEOUT`, `BROWSER_CRASHED` failures for Task 5.

- [ ] **Step 1: Write failing browser-operation and registry tests**

```python
async def test_worker_fills_selects_clicks_extracts_and_scrolls(page: Page) -> None:
    worker = BrowserWorker(page, LocatorResolver())
    await worker.navigate(controlled_url("query.html"))
    await worker.fill(search_ref, "codex")
    await worker.select(sort_ref, "newest")
    await worker.click(submit_ref)
    extracted = await worker.extract(result_ref)
    scrolled = await worker.scroll(200)

    assert extracted.data == "Result: codex (newest)"
    assert scrolled.ok is True
```

```python
async def test_registry_rejects_finish_as_a_browser_operation() -> None:
    result = await ToolRegistry(worker).execute(FinishAction(kind="finish", summary="done"))

    assert result.ok is False
    assert result.error is not None
    assert result.error.code is ErrorCode.MODEL_INVALID_ACTION
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `pytest tests/e2e/test_browser_worker.py tests/unit/test_tool_registry.py -q`

Expected: FAIL because the worker and registry do not exist.

- [ ] **Step 3: Implement atomic operations and structured error translation**

```python
async def fill(self, element: ElementRef, value: str) -> ToolResult:
    locator = await self._resolve(element)
    await locator.fill(value, timeout=self._timeout_ms)
    return ToolResult(ok=True, summary=f"Filled {element.element_id}.")
```

```python
async def execute(self, action: Action) -> ToolResult:
    match action:
        case NavigateAction():
            return await self._worker.navigate(action.url)
        case ClickAction():
            return await self._worker.click(action.element)
        case FillAction():
            return await self._worker.fill(action.element, action.value)
        case SelectAction():
            return await self._worker.select(action.element, action.value)
        case ExtractAction():
            return await self._worker.extract(action.element, action.attribute)
        case ScrollAction():
            return await self._worker.scroll(action.delta_y)
        case FinishAction():
            return _invalid_action_result("finish is handled by AgentRunner")
```

Each worker method catches only expected Playwright timeout, locator, and closed-target exceptions, converting them to safe `AgentError` data without exposing page values or stack traces. Other exceptions must be re-raised for the runner to classify as an unexpected browser failure.

- [ ] **Step 4: Run the focused tests to verify they pass**

Run: `pytest tests/e2e/test_browser_worker.py tests/unit/test_tool_registry.py -q`

Expected: PASS.

- [ ] **Step 5: Commit browser tools**

```bash
git add src/web_gui_agent/browser/browser_worker.py src/web_gui_agent/tools tests/e2e/test_browser_worker.py tests/unit/test_tool_registry.py
git commit -m "feat: add whitelisted browser tools"
```

### Task 5: Implement the minimal AgentRunner state machine and the controlled-page loop

**Files:**
- Create: `src/web_gui_agent/application/agent_runner.py`
- Create: `tests/fakes.py`
- Create: `tests/unit/test_agent_runner.py`
- Create: `tests/e2e/test_agent_runner.py`
- Modify: `src/web_gui_agent/browser/playwright_session.py`
- Modify: `src/web_gui_agent/domain/errors.py`

**Interfaces:**
- Consumes: `TaskRepository`, `Clock`, `ModelClient`, `BrowserRunFactory`, `BrowserRun`, `RunOutcome`, `Task.transition_to`, and the tool/observation implementation from Tasks 2–4.
- Produces: `AgentRunner.run(task_id, cancel_event) -> RunOutcome`, which persists task terminal state in the task repository and retains ordered observations and `StepRecord`s.

- [ ] **Step 1: Write failing runner tests for success and cleanup**

```python
async def test_runner_executes_scripted_query_and_records_each_step() -> None:
    outcome = await runner.run(task.id, asyncio.Event())

    assert outcome.task.status is TaskStatus.SUCCEEDED
    assert [step.action.kind for step in outcome.steps if step.action] == [
        "navigate", "fill", "select", "click", "extract", "finish",
    ]
    assert all(step.duration_ms >= 0 for step in outcome.steps)
    assert len(outcome.observations) == 6
    assert outcome.result is not None
    assert outcome.result.data == "Result: codex (newest)"
```

```python
async def test_runner_closes_context_and_marks_task_failed_when_action_raises() -> None:
    with pytest.raises(DomainError):
        await runner.run(task.id, asyncio.Event())

    assert fake_browser_run.closed is True
    assert (await repository.get(task.id)).status is TaskStatus.FAILED
```

The e2e test uses the local `query.html` site and `FakeModelClient` sequence `navigate`, `fill`, `select`, `click`, `extract`, `finish`; it asserts the query result and an isolated context is closed after the run. Add a unit assertion that the `AgentRunner` constructor annotation is `BrowserRunFactory`, not a Playwright `Page` type, so the application-to-browser boundary is exercised before implementation.

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `pytest tests/unit/test_agent_runner.py tests/e2e/test_agent_runner.py -q`

Expected: FAIL because `AgentRunner` and the browser-run integration do not exist.

- [ ] **Step 3: Implement the state machine with a mandatory cleanup path**

```python
async def run(self, task_id: str, cancel_event: asyncio.Event) -> RunOutcome:
    task = await self._load_and_mark_running(task_id)
    browser_run = await self._browser_runs.open()
    steps: list[StepRecord] = []
    observations: list[Observation] = []
    try:
        while True:
            self._raise_if_cancelled(cancel_event)
            observation = await browser_run.observe()
            observations.append(observation)
            action = await self._model.plan(
                task=task.input, observation=observation, memory={}, history=steps
            )
            if isinstance(action, FinishAction):
                return await self._succeed(task, steps, observations, action)
            result = await browser_run.execute(action)
            steps.append(self._step(action, result, observation))
            if not result.ok:
                raise DomainError(result.error or self._unexpected_error())
    except DomainError:
        await self._mark_failed_if_running(task)
        raise
    finally:
        await browser_run.close()
```

Record the finish action with a duration and final observation before transitioning to `SUCCEEDED`. Include an action count limit derived from task options so a scripted or model loop cannot run forever; expiry is a structured `ACTION_TIMEOUT` failure. In the Playwright browser run, compose `ObservationBuilder`, `BrowserWorker`, and `ToolRegistry` so all page interaction stays beneath the port boundary.

- [ ] **Step 4: Run the focused tests to verify they pass**

Run: `pytest tests/unit/test_agent_runner.py tests/e2e/test_agent_runner.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the runner loop**

```bash
git add src/web_gui_agent/application/agent_runner.py src/web_gui_agent/browser/playwright_session.py src/web_gui_agent/domain/errors.py tests/fakes.py tests/unit/test_agent_runner.py tests/e2e/test_agent_runner.py
git commit -m "feat: run single-page browser tasks"
```

### Task 6: Document phase-2 setup and run all project verification

**Files:**
- Modify: `README.md`
- Modify: `.env.example`
- Modify: `scripts/test.ps1`
- Create: `tests/unit/test_settings.py`

**Interfaces:**
- Consumes: phase-2 package imports, settings, test commands, and all public contracts from Tasks 1–5.
- Produces: reproducible Windows setup instructions and regression checks that keep browser dependencies outside the domain package.

- [ ] **Step 1: Write a failing browser-timeout configuration test**

```python
from web_gui_agent.config.settings import Settings


def test_browser_timeout_is_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEB_GUI_AGENT_BROWSER_TIMEOUT_MS", "4500")

    assert Settings().browser_timeout_ms == 4500
```

The existing `test_domain_imports.py` continues to prove that the new browser dependency did not leak into the domain package; the Task-5 runner test proves the application consumes `BrowserRunFactory` rather than a Playwright class.

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `pytest tests/unit/test_settings.py -q`

Expected: FAIL because `Settings` has no `browser_timeout_ms` field.

- [ ] **Step 3: Complete user-facing setup and test orchestration**

```powershell
uv sync --group dev
uv run playwright install chromium
.\scripts\test.ps1
```

Document these commands and the local controlled-page limitation in `README.md`. Add `WEB_GUI_AGENT_BROWSER_TIMEOUT_MS` to `.env.example` and `Settings`; pass it to the browser worker. Update `scripts/test.ps1` to retain existing static checks and run the e2e suite after `pytest` is available.

- [ ] **Step 4: Run the full verification suite**

Run: `ruff check .; mypy src tests; pyright; pytest`

Expected: all commands exit 0; pytest includes controlled Playwright lifecycle, observation, tool, and AgentRunner e2e coverage.

- [ ] **Step 5: Commit documentation and final regression checks**

```bash
git add README.md .env.example scripts/test.ps1 src/web_gui_agent/config/settings.py tests/unit/test_settings.py
git commit -m "docs: document phase two browser setup"
```

## Plan Self-Review

- **Spec coverage:** Task 1 establishes the typed action/run boundary; Task 2 owns independent Browser Context lifecycle and locator priority; Task 3 owns visible semantic observations; Task 4 owns all six named browser operations and whitelist dispatch; Task 5 owns the single-page Observe → Plan → Execute loop, step data, and cleanup; Task 6 provides local Windows setup and full static/e2e validation. Scheduler, action verification/retry, multi-tab, durable storage, and Page-Agent work are explicitly deferred to their designated later phases.
- **Placeholder scan:** The task steps specify concrete interfaces, commands, expected results, and commit contents. Future-phase exclusions are scope constraints, not unimplemented phase-2 requirements.
- **Type consistency:** `BrowserRunFactory.open()` creates `BrowserRun`; `AgentRunner` consumes only that port and `ModelClient`; `PlaywrightBrowserRunFactory` implements the port; the browser run composes the observation builder and tool registry. `RunOutcome` is the common return type.
- **Review-focus coverage:** launch failure and terminal re-run are covered in Task 5 unit tests; resolver ambiguity in Task 2; visibility filtering in Task 3; finish termination in Task 5. The test briefs must retain these cases when implementation begins.
