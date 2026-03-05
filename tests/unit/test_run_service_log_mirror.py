from __future__ import annotations

import logging
from pathlib import Path

import pytest

from server.runtime.logging.run_context import bind_run_logging_context, install_log_record_factory_once
from server.services.orchestration.run_service_log_mirror import RunServiceLogMirrorSession


@pytest.fixture(autouse=True)
def _isolate_root_handlers():
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    for handler in list(root.handlers):
        root.removeHandler(handler)
    root.setLevel(logging.INFO)
    try:
        yield
    finally:
        for handler in list(root.handlers):
            root.removeHandler(handler)
            handler.close()
        for handler in original_handlers:
            root.addHandler(handler)
        root.setLevel(original_level)


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def test_mirror_writes_only_matching_run_and_attempt(tmp_path: Path):
    install_log_record_factory_once()
    run_a = tmp_path / "run-a"
    run_b = tmp_path / "run-b"
    run_a.mkdir(parents=True, exist_ok=True)
    run_b.mkdir(parents=True, exist_ok=True)

    with RunServiceLogMirrorSession.open(run_dir=run_a, run_id="run-a", attempt_number=1), RunServiceLogMirrorSession.open(
        run_dir=run_b,
        run_id="run-b",
        attempt_number=1,
    ):
        with bind_run_logging_context(run_id="run-a", request_id="req-a", attempt_number=1):
            logging.getLogger("test").info("message-a")
        with bind_run_logging_context(run_id="run-b", request_id="req-b", attempt_number=1):
            logging.getLogger("test").info("message-b")
        with bind_run_logging_context(run_id="run-a", request_id="req-a", attempt_number=2):
            logging.getLogger("test").info("message-a-wrong-attempt")
        logging.getLogger("test").info("message-no-context")

    text_a = _read(run_a / ".audit" / "service.1.log")
    text_b = _read(run_b / ".audit" / "service.1.log")

    assert "message-a" in text_a
    assert "message-b" not in text_a
    assert "message-a-wrong-attempt" not in text_a
    assert "message-no-context" not in text_a

    assert "message-b" in text_b
    assert "message-a" not in text_b
    assert "message-no-context" not in text_b


def test_mirror_drops_records_without_run_id_context(tmp_path: Path):
    install_log_record_factory_once()
    run_dir = tmp_path / "run-c"
    run_dir.mkdir(parents=True, exist_ok=True)

    with RunServiceLogMirrorSession.open(run_dir=run_dir, run_id="run-c", attempt_number=1):
        logging.getLogger("test").info("dropped-no-context")

    text = _read(run_dir / ".audit" / "service.1.log")
    assert text == ""


def test_mirror_rotates_log_file(tmp_path: Path):
    install_log_record_factory_once()
    run_dir = tmp_path / "run-rotate"
    run_dir.mkdir(parents=True, exist_ok=True)

    with RunServiceLogMirrorSession.open(
        run_dir=run_dir,
        run_id="run-rotate",
        attempt_number=1,
        max_bytes=128,
        backup_count=3,
    ):
        for index in range(80):
            with bind_run_logging_context(run_id="run-rotate", request_id="req-rotate", attempt_number=1):
                logging.getLogger("rotate").info("line-%03d-%s", index, "x" * 40)

    audit_dir = run_dir / ".audit"
    rotated = sorted(path.name for path in audit_dir.glob("service.1.log*"))
    assert "service.1.log" in rotated
    assert any(name.endswith(".1") for name in rotated)
    assert len([name for name in rotated if name != "service.1.log"]) <= 3


def test_run_scope_is_superset_of_attempt_scope(tmp_path: Path):
    install_log_record_factory_once()
    run_dir = tmp_path / "run-full"
    run_dir.mkdir(parents=True, exist_ok=True)

    with RunServiceLogMirrorSession.open_run_scope(run_dir=run_dir, run_id="run-full"), RunServiceLogMirrorSession.open_attempt_scope(
        run_dir=run_dir,
        run_id="run-full",
        attempt_number=2,
    ):
        with bind_run_logging_context(run_id="run-full", request_id="req-full", attempt_number=None):
            logging.getLogger("scope").info("run-only")
        with bind_run_logging_context(run_id="run-full", request_id="req-full", attempt_number=2):
            logging.getLogger("scope").info("attempt-two")

    run_text = _read(run_dir / ".audit" / "service.run.log")
    attempt_text = _read(run_dir / ".audit" / "service.2.log")
    assert "run-only" in run_text
    assert "attempt-two" in run_text
    assert "run-only" not in attempt_text
    assert "attempt-two" in attempt_text
