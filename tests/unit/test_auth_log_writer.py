from pathlib import Path

from server.runtime.auth.log_writer import AuthLogWriter, NoopAuthLogWriter


def test_auth_log_writer_oauth_proxy_layout(tmp_path: Path):
    writer = AuthLogWriter(tmp_path)
    paths = writer.init_paths(transport="oauth_proxy", session_id="sid-1")
    assert paths.root == tmp_path / "oauth_proxy" / "sid-1"
    assert paths.events_path.exists()
    assert paths.primary_log_path.name == "http_trace.log"
    assert paths.secondary_log_path is None
    writer.append_event(paths, "session_started", {"status": "starting"})
    content = paths.events_path.read_text(encoding="utf-8")
    assert "\"type\": \"session_started\"" in content


def test_auth_log_writer_cli_delegate_layout(tmp_path: Path):
    writer = AuthLogWriter(tmp_path)
    paths = writer.init_paths(transport="cli_delegate", session_id="sid-2")
    assert paths.root == tmp_path / "cli_delegate" / "sid-2"
    assert paths.primary_log_path.name == "pty.log"
    assert paths.secondary_log_path is not None
    assert paths.secondary_log_path.name == "stdin.log"


def test_noop_auth_log_writer_uses_ephemeral_paths_and_cleans_up(tmp_path: Path):
    writer = NoopAuthLogWriter(tmp_path)
    paths = writer.init_paths(transport="oauth_proxy", session_id="sid-3")
    assert paths.persisted is False
    assert paths.root.exists()
    assert paths.primary_log_path.exists()
    writer.append_event(paths, "session_started", {"status": "starting"})
    assert not paths.events_path.exists()
    writer.cleanup_paths(paths)
    assert not paths.root.exists()
