import json
import logging
import os
import re
import sys
from datetime import datetime, timezone

from dotenv import dotenv_values


class JsonFormatter(logging.Formatter):
    def __init__(self, secrets=()):
        super().__init__()
        self.secrets = tuple(value for value in secrets if value)

    def format(self, record):
        message = record.getMessage()
        for value in self.secrets:
            message = message.replace(value, "[REDACTED]")
        message = re.sub(r"(://[^\s:/]+:)[^\s@]+@", r"\1[REDACTED]@", message)
        message = re.sub(r"(?i)([?&](?:key|api_key)=)[^&\s]+", r"\1[REDACTED]", message)
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": message,
        }
        for name in ("execution_id", "step_id", "status", "event"):
            if hasattr(record, name):
                payload[name] = str(getattr(record, name))
        # Raw exception messages/tracebacks may include prompts, documents or keys.
        if record.exc_info and record.exc_info[1] is not None:
            payload["exception"] = type(record.exc_info[1]).__name__
        return json.dumps(payload)


def configure_logging():
    values = {**dotenv_values(".env"), **os.environ}
    secrets = [values.get(name) for name in
               ("GOOGLE_API_KEY", "POSTGRES_PASSWORD", "DATABASE_URL")]
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(secrets))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers = []
        logger.propagate = True
    # SDK logs must not expand into raw requests, prompts, or responses.
    for name in ("google", "langchain_google_genai", "httpx", "httpcore", "httpx2"):
        logging.getLogger(name).setLevel(logging.ERROR)
