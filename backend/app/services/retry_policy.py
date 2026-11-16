"""Bounded retries for AI provider calls.

Only failures that are likely to succeed on a later attempt are retried:
timeouts, dropped connections, rate limits (429), request timeouts (408), and
provider-side errors (5xx such as "503 high demand"). Bad requests, invalid
credentials, and malformed output fail immediately.
"""

import httpx
from tenacity import (
    retry, retry_if_exception_type, stop_after_attempt, wait_exponential,
)

TRANSIENT_STATUS = {408, 429, 500, 502, 503, 504}


class TemporaryAIError(Exception):
    """The AI provider was unavailable after all retry attempts."""


def _status(exc: BaseException) -> int | None:
    for attr in ("code", "status_code"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    response = getattr(exc, "response", None)
    value = getattr(response, "status_code", None)
    return value if isinstance(value, int) else None


def is_transient(exc: BaseException) -> bool:
    """Inspect the exception and its causes; SDKs often wrap the original error."""
    seen = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, (TimeoutError, ConnectionError, httpx.TimeoutException, httpx.NetworkError)):
            return True
        if _status(current) in TRANSIENT_STATUS:
            return True
        current = current.__cause__ or current.__context__
    return False


@retry(
    retry=retry_if_exception_type(TemporaryAIError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    reraise=True,
)
def invoke_ai_with_retry(graph, facts):
    try:
        return graph.invoke({"invoice_facts": facts})
    except Exception as exc:
        if is_transient(exc):
            raise TemporaryAIError("Temporary AI service failure") from exc
        raise
