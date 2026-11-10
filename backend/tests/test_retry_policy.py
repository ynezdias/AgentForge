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
