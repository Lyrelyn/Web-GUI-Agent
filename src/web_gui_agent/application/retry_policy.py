"""Bounded retry decisions for structured agent failures."""

from web_gui_agent.domain.errors import AgentError, ErrorCode


class RetryPolicy:
    """Allows only idempotent, recoverable error categories to re-plan."""

    _RECOVERABLE_CODES = frozenset(
        {ErrorCode.LOCATOR_NOT_FOUND, ErrorCode.ACTION_TIMEOUT, ErrorCode.MODEL_INVALID_ACTION}
    )

    def should_retry(self, error: AgentError, *, attempt: int, max_retries: int) -> bool:
        return (
            attempt < max_retries
            and (error.retryable or error.code in self._RECOVERABLE_CODES)
            and error.code is not ErrorCode.VERIFICATION_FAILED
        )
