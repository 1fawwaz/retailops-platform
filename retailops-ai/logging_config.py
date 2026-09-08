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
request_context_var: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "request_context", default=None
)


class ExecutionIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.execution_id = execution_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        ctx = request_context_var.get() or {}
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", ctx.get("request_id")),
            "execution_id": getattr(record, "execution_id", execution_id_var.get()),
            "conversation_id": getattr(record, "conversation_id", ctx.get("conversation_id")),
            "agent_name": getattr(record, "agent_name", ctx.get("agent_name")),
            "tool_name": getattr(record, "tool_name", ctx.get("tool_name")),
            "latency": getattr(record, "latency", ctx.get("latency")),
            "sql_time": getattr(record, "sql_time", ctx.get("sql_time")),
            "llm_time": getattr(record, "llm_time", ctx.get("llm_time")),
            "token_counts": getattr(record, "token_counts", ctx.get("token_counts")),
            "provider": getattr(record, "provider", ctx.get("provider")),
            "retry_count": getattr(record, "retry_count", ctx.get("retry_count", 0)),
            "fallback_used": getattr(record, "fallback_used", ctx.get("fallback_used", False)),
            "citations": getattr(record, "citations", ctx.get("citations")),
            "validation_result": getattr(record, "validation_result", ctx.get("validation_result")),
            "errors": getattr(record, "errors", ctx.get("errors")),
            "recommendation_ids": getattr(
                record, "recommendation_ids", ctx.get("recommendation_ids")
            ),
            "user_id": getattr(record, "user_id", ctx.get("user_id")),
            "decision_id": getattr(record, "decision_id", ctx.get("decision_id")),
            "history_mode": getattr(record, "history_mode", ctx.get("history_mode", "live")),
            "confidence_method": getattr(
                record, "confidence_method", ctx.get("confidence_method", "global")
            ),
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


def set_execution_id_safe(execution_id: str | None) -> None:
    """Safely set or clear the execution_id context variable without
    relying on token reset across async/thread-pool boundaries.
    """
    execution_id_var.set(execution_id)
