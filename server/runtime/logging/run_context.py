from __future__ import annotations

import contextlib
import contextvars
import logging
from typing import Iterator

_RUN_ID_CTX: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "runtime_logging_run_id",
    default=None,
)
_REQUEST_ID_CTX: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "runtime_logging_request_id",
    default=None,
)
_ATTEMPT_NUMBER_CTX: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    "runtime_logging_attempt_number",
    default=None,
)
_PHASE_CTX: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "runtime_logging_phase",
    default=None,
)

_LOG_RECORD_FACTORY_INSTALLED = False


@contextlib.contextmanager
def bind_run_logging_context(
    *,
    run_id: str | None,
    request_id: str | None,
    attempt_number: int | None,
    phase: str | None = None,
) -> Iterator[None]:
    run_token = _RUN_ID_CTX.set(run_id)
    request_token = _REQUEST_ID_CTX.set(request_id)
    attempt_token = _ATTEMPT_NUMBER_CTX.set(attempt_number)
    phase_token = _PHASE_CTX.set(phase)
    try:
        yield
    finally:
        _PHASE_CTX.reset(phase_token)
        _ATTEMPT_NUMBER_CTX.reset(attempt_token)
        _REQUEST_ID_CTX.reset(request_token)
        _RUN_ID_CTX.reset(run_token)


@contextlib.contextmanager
def bind_request_logging_context(
    *,
    request_id: str | None,
    phase: str | None = None,
) -> Iterator[None]:
    request_token = _REQUEST_ID_CTX.set(request_id)
    phase_token = _PHASE_CTX.set(phase)
    try:
        yield
    finally:
        _PHASE_CTX.reset(phase_token)
        _REQUEST_ID_CTX.reset(request_token)


def get_logging_context() -> dict[str, object | None]:
    return {
        "run_id": _RUN_ID_CTX.get(),
        "request_id": _REQUEST_ID_CTX.get(),
        "attempt_number": _ATTEMPT_NUMBER_CTX.get(),
        "phase": _PHASE_CTX.get(),
    }


def install_log_record_factory_once() -> None:
    global _LOG_RECORD_FACTORY_INSTALLED
    if _LOG_RECORD_FACTORY_INSTALLED:
        return

    previous_factory = logging.getLogRecordFactory()

    def _factory(*args: object, **kwargs: object) -> logging.LogRecord:
        record = previous_factory(*args, **kwargs)
        if not hasattr(record, "run_id"):
            setattr(record, "run_id", _RUN_ID_CTX.get())
        if not hasattr(record, "request_id"):
            setattr(record, "request_id", _REQUEST_ID_CTX.get())
        if not hasattr(record, "attempt_number"):
            setattr(record, "attempt_number", _ATTEMPT_NUMBER_CTX.get())
        if not hasattr(record, "phase"):
            setattr(record, "phase", _PHASE_CTX.get())
        return record

    logging.setLogRecordFactory(_factory)
    _LOG_RECORD_FACTORY_INSTALLED = True
