import pytest

from app.services.retry_policy import invoke_ai_with_retry, TemporaryAIError


@pytest.mark.parametrize("error", [TimeoutError, ConnectionError])
def test_retry_after_temporary_failure(error):
    class FakeGraph:
        calls = 0

        def invoke(self, state):
            self.calls += 1
            if self.calls < 3:
                raise error("Temporary failure")
            return {"investigation": {"risk_level": "HIGH"}}

    graph = FakeGraph()
    delays = []
    result = invoke_ai_with_retry.retry_with(sleep=delays.append)(graph, {"invoice_id": "test"})
    assert graph.calls == 3
    assert delays == [1, 2]
    assert result["investigation"]["risk_level"] == "HIGH"


def test_permanent_failure_not_retried():
    class FakeGraph:
        calls = 0

        def invoke(self, state):
            self.calls += 1
            raise ValueError("Invalid request")

    graph = FakeGraph()
    with pytest.raises(ValueError, match="Invalid request"):
        invoke_ai_with_retry.retry_with(sleep=lambda _: None)(graph, {})
    assert graph.calls == 1


def test_exhausted_retries_raise_temporary_ai_error():
    class FakeGraph:
        calls = 0

        def invoke(self, state):
            self.calls += 1
            raise TimeoutError("Temporary timeout")

    graph = FakeGraph()
    with pytest.raises(TemporaryAIError, match="Temporary AI service failure"):
        invoke_ai_with_retry.retry_with(sleep=lambda _: None)(graph, {})
    assert graph.calls == 3


def _google_errors():
    from google.genai.errors import ClientError, ServerError
    body = lambda code, status: {"error": {"code": code, "message": "m", "status": status}}
    return ClientError, ServerError, body


def _wrapped_like_langchain(error):
    """Reproduce how langchain-google-genai re-raises a ServerError."""
    from langchain_google_genai.chat_models import GoogleAPIError
    try:
        try:
            raise error
        except Exception as inner:
            raise GoogleAPIError(code=inner.code, response_json=inner.details, response=None) from inner
    except Exception as outer:
        return outer


def test_classifies_provider_errors():
    from app.services.retry_policy import is_transient
    ClientError, ServerError, body = _google_errors()
    high_demand = ServerError(503, body(503, "UNAVAILABLE"))
    assert is_transient(high_demand)
    assert is_transient(_wrapped_like_langchain(high_demand))  # The Step 1 failure.
    assert is_transient(ClientError(429, body(429, "RESOURCE_EXHAUSTED")))
    assert not is_transient(ClientError(400, body(400, "INVALID_ARGUMENT")))
    assert not is_transient(ClientError(403, body(403, "PERMISSION_DENIED")))  # Bad key: don't hammer.
    assert not is_transient(ValueError("schema mismatch"))
    import httpx
    assert is_transient(httpx.ReadTimeout("slow"))


def test_high_demand_is_retried_then_succeeds():
    _, ServerError, body = _google_errors()

    class FlakyGraph:
        calls = 0

        def invoke(self, state):
            self.calls += 1
            if self.calls < 3:
                raise _wrapped_like_langchain(ServerError(503, body(503, "UNAVAILABLE")))
            return {"investigation": {"risk_level": "HIGH"}}

    graph = FlakyGraph()
    result = invoke_ai_with_retry.retry_with(sleep=lambda _: None)(graph, {})
    assert graph.calls == 3 and result["investigation"]["risk_level"] == "HIGH"
