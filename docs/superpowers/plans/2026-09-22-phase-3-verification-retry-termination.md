# Phase 3 Verification, Retry, and Termination Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make browser-run outcomes independently verifiable and ensure recoverable failures, cancellation, and deadline expiry reach a consistent terminal state.

**Architecture:** Four small verification components evaluate the before/after observations around one typed action; an `ActionVerifier` is their only application-facing entry point. `AgentRunner` owns the state machine, retry decisions, deadline, and cleanup, while `DeepSeekModelClient` remains an infrastructure adapter behind the existing `ModelClient` protocol.

**Tech Stack:** Python 3.12, Pydantic v2, asyncio, Playwright, OpenAI-compatible DeepSeek API, pytest.

**Spec:** `设计文档.md` (sections 3–5, Phase 3)

## Global Constraints

- Domain and application packages must not import Playwright, FastAPI, an HTTP SDK, or a concrete model client.
- Browser actions remain typed `Action` values and continue through the tool whitelist.
- Model keys, cookies, tokens, and fill values must not appear in persisted records, logs, or API responses.
- Task states only move `QUEUED -> RUNNING -> {SUCCEEDED, FAILED, CANCELLED, NEEDS_CONFIRMATION}`.
- A task has one `asyncio.timeout()` deadline from `TaskOptions.timeout_ms`; all paths close the task Browser Context.
- A retry is allowed only for a retryable structured error and never exceeds `TaskOptions.max_retries`.

## Review Focus

- A browser factory failing before it returns a run must still leave the task terminal rather than `RUNNING`.
- A cancellation arriving between planning and tool dispatch must prevent that dispatch.
- A timeout while a browser operation is in flight must close its context and report one terminal failure.
- A `FinishAction` with unsupported or absent browser evidence must not turn a task into `SUCCEEDED`.
- A malformed upstream DeepSeek response must produce `MODEL_INVALID_ACTION`, not leak the response body or API key.

---

### Task 1: Verification contracts and pure verifiers

**Files:**
- Create: `src/web_gui_agent/verification/{__init__.py,url_verifier.py,dom_verifier.py,form_verifier.py,feedback_verifier.py,action_verifier.py}`
- Modify: `src/web_gui_agent/domain/{action.py,observation.py}`
- Test: `tests/unit/test_action_verifier.py`

**Interfaces:**
- Consumes: `Action`, `ToolResult`, and before/after `Observation`.
- Produces: `ActionVerifier.verify(before, action, result, after) -> VerificationResult`.

- [ ] **Step 1: Write failing tests** for successful navigation URL evidence, filled/select element value evidence, a changed post-click DOM, page error feedback, and a finish action whose expected text is absent.
- [ ] **Step 2: Run** `pytest tests/unit/test_action_verifier.py -q` and confirm imports or assertions fail before the verifier exists.
- [ ] **Step 3: Implement** the immutable `FinishAction.expected_text`, observable `ElementCandidate.value`, the four focused verifier classes, and `ActionVerifier` that returns structured evidence and reports `VERIFICATION_FAILED` through a failed result.
- [ ] **Step 4: Run** `pytest tests/unit/test_action_verifier.py -q` and confirm all verification cases pass.

### Task 2: Retry policy and verified runner state machine

**Files:**
- Create: `src/web_gui_agent/application/retry_policy.py`
- Modify: `src/web_gui_agent/application/agent_runner.py`, `src/web_gui_agent/domain/errors.py`, `src/web_gui_agent/domain/run.py`
- Test: `tests/unit/test_retry_policy.py`, `tests/unit/test_agent_runner.py`

**Interfaces:**
- Consumes: Task 1 `ActionVerifier.verify`, task options, `BrowserRun`, and `ModelClient`.
- Produces: `RetryPolicy.should_retry(error, attempt, max_retries) -> bool` and `AgentRunner.run()` with verified records and terminal task state.

- [ ] **Step 1: Write failing tests** for retrying one locator failure then succeeding, stopping after configured retries, cancellation before execute yielding `CANCELLED`, deadline expiry yielding `ACTION_TIMEOUT`, verification failure yielding `FAILED`, and browser-open failure yielding `FAILED`.
- [ ] **Step 2: Run** `pytest tests/unit/test_retry_policy.py tests/unit/test_agent_runner.py -q` and confirm the new expectations fail.
- [ ] **Step 3: Implement** retryable error classification, bounded re-observation/re-planning, `asyncio.timeout`, cancellation checks before both plan and execute, verification after every successful non-finish action, evidence-backed finish success, and safe terminal updates/cleanup.
- [ ] **Step 4: Run** `pytest tests/unit/test_retry_policy.py tests/unit/test_agent_runner.py -q` and confirm every runner terminal path passes.

### Task 3: Browser evidence and structured browser errors

**Files:**
- Modify: `src/web_gui_agent/browser/{observation_builder.py,browser_worker.py,playwright_session.py}`, `src/web_gui_agent/domain/ports/browser_run.py`
- Test: `tests/unit/test_observation_builder.py`, `tests/e2e/test_browser_worker.py`

**Interfaces:**
- Consumes: Task 1 `ElementCandidate.value` and stable `AgentError` codes.
- Produces: observations that include safe form values and browser errors marked retryable only where recovery is appropriate.

- [ ] **Step 1: Write failing tests** for visible non-secret input value capture, disabled/hidden filtering, page error signal capture, and a locator failure yielding retryable `LOCATOR_NOT_FOUND`.
- [ ] **Step 2: Run** `pytest tests/unit/test_observation_builder.py tests/e2e/test_browser_worker.py -q` and confirm the missing observations/error flags fail.
- [ ] **Step 3: Implement** the DOM payload additions and error retryability mapping without changing the browser port surface.
- [ ] **Step 4: Run** `pytest tests/unit/test_observation_builder.py tests/e2e/test_browser_worker.py -q` and confirm the controlled browser flow passes.

### Task 4: DeepSeek model adapter and local configuration

**Files:**
- Create: `src/web_gui_agent/infrastructure/model/{__init__.py,deepseek_client.py}`
- Modify: `pyproject.toml`, `src/web_gui_agent/config/settings.py`, `.env.example`, `src/web_gui_agent/composition_root.py`, `README.md`
- Test: `tests/unit/test_deepseek_client.py`, `tests/unit/test_settings.py`

**Interfaces:**
- Consumes: `Settings.deepseek_api_key`, `Settings.deepseek_model`, and OpenAI-compatible async responses.
- Produces: `DeepSeekModelClient.plan(...) -> Action`, mapping invalid JSON/schema/provider errors to `DomainError(AgentError(MODEL_INVALID_ACTION))`.

- [ ] **Step 1: Write failing tests** with a narrow fake OpenAI-compatible client for a valid JSON action, malformed action JSON, and missing API key configuration.
- [ ] **Step 2: Run** `pytest tests/unit/test_deepseek_client.py tests/unit/test_settings.py -q` and confirm the adapter/settings do not yet exist.
- [ ] **Step 3: Implement** a dependency-injected `AsyncOpenAI` adapter with DeepSeek base URL, JSON-only action prompt, Pydantic `Action` validation, stable safe error mapping, and lazy production assembly so API startup does not require a key until runs are enabled.
- [ ] **Step 4: Run** `pytest tests/unit/test_deepseek_client.py tests/unit/test_settings.py -q` and confirm valid and invalid response behavior.

### Task 5: Stage-three regression and documentation

**Files:**
- Create: `tests/e2e/test_agent_runner.py`, `tests/fixtures/web_app/query.html`
- Modify: `scripts/test.ps1`, `README.md`
- Test: `tests/e2e/test_agent_runner.py`

**Interfaces:**
- Consumes: Tasks 1–4 through the concrete Playwright run and fake model sequence.
- Produces: a controlled end-to-end proof that verified query extraction succeeds and cancelled/failed runs close their context.

- [ ] **Step 1: Write a failing e2e test** that runs navigate, fill, select, click, extract, and evidence-backed finish against a local controlled page and asserts verification records and `SUCCEEDED`.
- [ ] **Step 2: Run** `pytest tests/e2e/test_agent_runner.py -q` and confirm it fails before the fixture/runner behavior is complete.
- [ ] **Step 3: Add** the controlled page and minimal fixture, then update README with `uv sync --group dev`, `uv run playwright install chromium`, DeepSeek environment variables, and the exact local validation command.
- [ ] **Step 4: Run** `ruff check .`, `mypy src tests`, `pyright`, and `pytest`; confirm all pass before completion.
