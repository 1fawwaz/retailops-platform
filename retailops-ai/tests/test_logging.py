import json
import logging

from logging_config import (
    JsonFormatter,
    bind_execution_id,
    execution_id_var,
    reset_execution_id,
)


def _make_record(message: str) -> logging.LogRecord:
    return logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=(),
        exc_info=None,
    )


def test_json_formatter_produces_valid_json_with_expected_fields() -> None:
    record = _make_record("hello")
    record.execution_id = "exec-123"

    line = JsonFormatter().format(record)
    payload = json.loads(line)

    assert payload["message"] == "hello"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "test.logger"
    assert payload["execution_id"] == "exec-123"
    assert "timestamp" in payload


def test_json_formatter_execution_id_defaults_to_none_when_unset() -> None:
    record = _make_record("no execution bound")

    payload = json.loads(JsonFormatter().format(record))

    assert payload["execution_id"] is None


def test_bind_execution_id_sets_and_resets_the_contextvar() -> None:
    assert execution_id_var.get() is None

    token = bind_execution_id("exec-abc")
    try:
        assert execution_id_var.get() == "exec-abc"
    finally:
        reset_execution_id(token)

    assert execution_id_var.get() is None


def test_every_log_line_emitted_through_the_filter_carries_execution_id() -> None:
    from logging_config import ExecutionIdFilter

    logger = logging.getLogger("test.execution_id_filter")
    logger.addFilter(ExecutionIdFilter())

    token = bind_execution_id("exec-xyz")
    try:
        record = _make_record("bound message")
        assert logger.filter(record) is True
        assert record.execution_id == "exec-xyz"  # type: ignore[attr-defined]
    finally:
        reset_execution_id(token)
