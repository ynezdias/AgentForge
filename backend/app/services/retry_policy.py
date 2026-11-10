from tenacity import (
    retry, retry_if_exception_type, stop_after_attempt, wait_exponential,
)


class TemporaryAIError(Exception):
    pass


@retry(
    retry=retry_if_exception_type(TemporaryAIError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    reraise=True,
)
def invoke_ai_with_retry(graph, facts):
    try:
        return graph.invoke({"invoice_facts": facts})
    except (TimeoutError, ConnectionError) as exc:
        raise TemporaryAIError("Temporary AI service failure") from exc
