from __future__ import annotations

import logging

from server.runtime.logging.run_context import bind_run_logging_context
from server.runtime.logging.structured_trace import log_event


def test_log_event_uses_run_context_and_formats_kv(caplog) -> None:
    logger = logging.getLogger("tests.structured_trace")
    with bind_run_logging_context(
        run_id="run-123",
        request_id="req-123",
        attempt_number=2,
        phase="run_lifecycle",
    ):
        with caplog.at_level(logging.INFO, logger=logger.name):
            log_event(
                logger,
                event="run.lifecycle.started",
                phase="run_lifecycle",
                outcome="start",
                engine="opencode",
            )
    assert caplog.records
    message = caplog.records[-1].getMessage()
    assert 'event="run.lifecycle.started"' in message
    assert 'request_id="req-123"' in message
    assert 'run_id="run-123"' in message
    assert "attempt=2" in message
    assert 'phase="run_lifecycle"' in message
    assert 'outcome="start"' in message
    assert 'engine="opencode"' in message


def test_log_event_redacts_sensitive_values(caplog) -> None:
    logger = logging.getLogger("tests.structured_trace.redact")
    with caplog.at_level(logging.INFO, logger=logger.name):
        log_event(
            logger,
            event="auth.input.accepted",
            phase="auth_orchestration",
            outcome="ok",
            request_id="req-321",
            api_key="secret-value",
            authorization_code="abc123",
        )
    message = caplog.records[-1].getMessage()
    assert "secret-value" not in message
    assert "abc123" not in message
    assert "api_key=" in message
    assert "authorization_code=" in message
