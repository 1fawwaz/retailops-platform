"""Structured JSON logging. Every line carries the execution_id of the
agent run it belongs to (None outside of one, e.g. startup logs), via a
contextvar rather than threading execution_id through every log call
site -- CLAUDE.md invariant 2 (full trace) requires the association to
exist on every line, not just on the ones a developer remembered to tag.
"""

import contextvars
import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

execution_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "execution_id", default=None
)


class ExecutionIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.execution_id = execution_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "execution_id": getattr(record, "execution_id", None),
        }
        if record.exc_info is not None:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(ExecutionIdFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def bind_execution_id(execution_id: str) -> contextvars.Token[str | None]:
    """Call at the start of an agent execution; pair with reset_execution_id
    in a finally block so the id doesn't leak into unrelated log lines once
    the execution ends.
    """
    return execution_id_var.set(execution_id)


def reset_execution_id(token: contextvars.Token[str | None]) -> None:
    execution_id_var.reset(token)
