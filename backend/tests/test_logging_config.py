import json
import logging
import sys

from app.core.logging_config import JsonFormatter


def test_json_log_has_structured_fields_and_redacts_secrets():
    record = logging.LogRecord("app.workflow", logging.INFO, __file__, 1,
                               "token=%s url=postgresql://user:password@postgres/db?key=other",
                               ("test-secret",), None)
    record.execution_id = "execution-123"
    record.status = "RUNNING"
    value = json.loads(JsonFormatter(["test-secret"]).format(record))
    assert value["execution_id"] == "execution-123"
    assert value["status"] == "RUNNING"
    assert value["timestamp"]
    assert value["level"] == "INFO"
    assert "test-secret" not in value["message"]
    assert "password" not in value["message"]
    assert "other" not in value["message"]


def test_exception_logs_do_not_include_private_exception_content():
    try:
        raise ValueError("private invoice document and API key")
    except ValueError:
        record = logging.LogRecord("app.workflow", logging.ERROR, __file__, 1,
                                   "workflow_failed", (), sys.exc_info())
    value = json.loads(JsonFormatter().format(record))
    assert value["exception"] == "ValueError"
    assert "private invoice" not in str(value)
