from web_gui_agent.application.retry_policy import RetryPolicy
from web_gui_agent.domain.errors import AgentError, ErrorCode


def test_retry_policy_retries_recoverable_locator_failure_within_budget() -> None:
    error = AgentError(code=ErrorCode.LOCATOR_NOT_FOUND, message="Missing", retryable=True)

    assert RetryPolicy().should_retry(error, attempt=0, max_retries=1) is True
    assert RetryPolicy().should_retry(error, attempt=1, max_retries=1) is False


def test_retry_policy_does_not_retry_verification_failure() -> None:
    error = AgentError(code=ErrorCode.VERIFICATION_FAILED, message="No evidence")

    assert RetryPolicy().should_retry(error, attempt=0, max_retries=2) is False
