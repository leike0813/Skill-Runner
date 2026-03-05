import json
import logging
from logging.handlers import TimedRotatingFileHandler

import pytest

from server import logging_config
from server.runtime.logging.run_context import bind_run_logging_context
from server.services.platform.system_settings_service import EditableLoggingSettings


@pytest.fixture(autouse=True)
def _isolate_root_logger():
    root = logging.getLogger()
    aps_logger = logging.getLogger("apscheduler")
    original_handlers = list(root.handlers)
    original_level = root.level
    original_aps_level = aps_logger.level
    had_flag = hasattr(root, logging_config._LOGGING_CONFIGURED_ATTR)
    original_flag = getattr(root, logging_config._LOGGING_CONFIGURED_ATTR, None)

    for handler in list(root.handlers):
        root.removeHandler(handler)

    if had_flag:
        delattr(root, logging_config._LOGGING_CONFIGURED_ATTR)

    try:
        yield
    finally:
        for handler in list(root.handlers):
            root.removeHandler(handler)
            if handler not in original_handlers:
                handler.close()

        for handler in original_handlers:
            root.addHandler(handler)
        root.setLevel(original_level)
        aps_logger.setLevel(original_aps_level)

        if had_flag:
            setattr(root, logging_config._LOGGING_CONFIGURED_ATTR, original_flag)
        elif hasattr(root, logging_config._LOGGING_CONFIGURED_ATTR):
            delattr(root, logging_config._LOGGING_CONFIGURED_ATTR)


def _stub_logging_settings(
    monkeypatch,
    *,
    level: str = "INFO",
    output_format: str = "text",
    retention_days: int = 7,
    dir_max_bytes: int = 1024 * 1024,
):
    monkeypatch.setattr(
        logging_config.system_settings_service,
        "get_logging_settings",
        lambda: EditableLoggingSettings(
            level=level,
            format=output_format,
            retention_days=retention_days,
            dir_max_bytes=dir_max_bytes,
        ),
    )


def test_setup_logging_installs_stream_and_timed_file_handler(monkeypatch, tmp_path):
    _stub_logging_settings(monkeypatch, level="INFO", retention_days=7)
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    monkeypatch.setenv("LOG_FILE_BASENAME", "skill_runner.log")

    logging_config.setup_logging()

    root = logging.getLogger()
    timed_handlers = [h for h in root.handlers if isinstance(h, TimedRotatingFileHandler)]
    stream_handlers = [h for h in root.handlers if type(h) is logging.StreamHandler]

    assert len(timed_handlers) == 1
    assert len(stream_handlers) == 1
    assert timed_handlers[0].backupCount == 7
    assert timed_handlers[0].when == "MIDNIGHT"


def test_setup_logging_is_idempotent(monkeypatch, tmp_path):
    _stub_logging_settings(monkeypatch)
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    monkeypatch.setenv("LOG_FILE_BASENAME", "skill_runner.log")

    logging_config.setup_logging()
    first_ids = [id(handler) for handler in logging.getLogger().handlers]
    logging_config.setup_logging()
    second_ids = [id(handler) for handler in logging.getLogger().handlers]

    assert first_ids == second_ids


def test_setup_logging_keeps_record_factory_idempotent(monkeypatch, tmp_path):
    _stub_logging_settings(monkeypatch)
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    monkeypatch.setenv("LOG_FILE_BASENAME", "skill_runner.log")

    logging_config.setup_logging()
    first_factory = logging.getLogRecordFactory()
    logging_config.setup_logging()
    second_factory = logging.getLogRecordFactory()

    assert first_factory is second_factory


def test_setup_logging_json_format_writes_expected_fields(monkeypatch, tmp_path):
    _stub_logging_settings(monkeypatch, output_format="json")
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    monkeypatch.setenv("LOG_FILE_BASENAME", "skill_runner.log")
    monkeypatch.setenv("LOG_LEVEL", "CRITICAL")

    logging_config.setup_logging()
    root = logging.getLogger()
    root.info("json-payload")

    for handler in root.handlers:
        if hasattr(handler, "flush"):
            handler.flush()

    payload = json.loads((tmp_path / "skill_runner.log").read_text(encoding="utf-8").strip().splitlines()[-1])
    assert payload["message"] == "json-payload"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "root"
    assert "timestamp" in payload


def test_setup_logging_falls_back_to_stream_only_when_file_handler_fails(monkeypatch, tmp_path, capsys):
    _stub_logging_settings(monkeypatch)
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    monkeypatch.setenv("LOG_FILE_BASENAME", "skill_runner.log")

    class _BrokenHandler:
        def __init__(self, *args, **kwargs):
            raise OSError("disk-full")

    monkeypatch.setattr(logging_config, "QuotaTimedRotatingFileHandler", _BrokenHandler)

    logging_config.setup_logging()

    root = logging.getLogger()
    assert all(not isinstance(handler, TimedRotatingFileHandler) for handler in root.handlers)
    assert any(type(handler) is logging.StreamHandler for handler in root.handlers)

    captured = capsys.readouterr()
    assert "fallback=stream_only" in captured.err


def test_setup_logging_defaults_apscheduler_to_warning(monkeypatch, tmp_path):
    _stub_logging_settings(monkeypatch, level="INFO")
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    monkeypatch.setenv("LOG_FILE_BASENAME", "skill_runner.log")

    logging_config.setup_logging()

    assert logging.getLogger("apscheduler").level == logging.WARNING


def test_setup_logging_raises_apscheduler_to_info_under_debug(monkeypatch, tmp_path):
    _stub_logging_settings(monkeypatch, level="DEBUG")
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    monkeypatch.setenv("LOG_FILE_BASENAME", "skill_runner.log")

    logging_config.setup_logging()

    assert logging.getLogger("apscheduler").level == logging.INFO


def test_reload_logging_from_settings_replaces_managed_handlers(monkeypatch, tmp_path):
    _stub_logging_settings(monkeypatch, level="INFO")
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    monkeypatch.setenv("LOG_FILE_BASENAME", "skill_runner.log")

    logging_config.setup_logging()
    first_ids = [id(handler) for handler in logging.getLogger().handlers]

    _stub_logging_settings(monkeypatch, level="DEBUG", output_format="json", retention_days=3, dir_max_bytes=2048)
    logging_config.reload_logging_from_settings()
    second_handlers = list(logging.getLogger().handlers)
    second_ids = [id(handler) for handler in second_handlers]
    timed_handler = next(handler for handler in second_handlers if isinstance(handler, TimedRotatingFileHandler))

    assert first_ids != second_ids
    assert timed_handler.backupCount == 3
    assert logging.getLogger().level == logging.DEBUG


def test_logging_settings_payload_uses_settings_file_for_editable_and_env_for_read_only(monkeypatch, tmp_path):
    _stub_logging_settings(monkeypatch, level="WARNING", output_format="json", retention_days=9, dir_max_bytes=4096)
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    monkeypatch.setenv("LOG_FILE_BASENAME", "custom.log")
    monkeypatch.setenv("LOG_ROTATION_WHEN", "H")
    monkeypatch.setenv("LOG_ROTATION_INTERVAL", "2")

    payload = logging_config.get_logging_settings_payload()

    assert payload["editable"]["level"] == "WARNING"
    assert payload["editable"]["format"] == "json"
    assert payload["editable"]["retention_days"] == 9
    assert payload["editable"]["dir_max_bytes"] == 4096
    assert payload["read_only"]["dir"] == str(tmp_path)
    assert payload["read_only"]["file_basename"] == "custom.log"
    assert payload["read_only"]["rotation_when"] == "H"
    assert payload["read_only"]["rotation_interval"] == 2


def test_setup_logging_installs_run_context_record_factory(monkeypatch, tmp_path):
    _stub_logging_settings(monkeypatch)
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    monkeypatch.setenv("LOG_FILE_BASENAME", "skill_runner.log")

    captured: list[logging.LogRecord] = []

    class _CaptureHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured.append(record)

    logging_config.setup_logging()
    root = logging.getLogger()
    capture_handler = _CaptureHandler()
    root.addHandler(capture_handler)
    try:
        with bind_run_logging_context(run_id="run-1", request_id="req-1", attempt_number=2):
            logging.getLogger("test").info("hello")
    finally:
        root.removeHandler(capture_handler)

    assert captured
    record = captured[-1]
    assert getattr(record, "run_id", None) == "run-1"
    assert getattr(record, "request_id", None) == "req-1"
    assert getattr(record, "attempt_number", None) == 2
