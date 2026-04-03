from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

from server.services.engine_management.agent_cli_manager import CommandResult


def _load_agent_manager_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "agent_manager.py"
    spec = importlib.util.spec_from_file_location("agent_manager_script", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_summarize_output_masks_sensitive_values() -> None:
    module = _load_agent_manager_module()
    text = "token=abc123\nclient_secret:xyz456\nnormal line"
    summary = module._summarize_output(text)
    assert "abc123" not in summary
    assert "xyz456" not in summary
    assert "token=***" in summary
    assert "client_secret=***" in summary


def test_ensure_with_diagnostics_reports_partial_failure() -> None:
    module = _load_agent_manager_module()

    class FakeManager:
        def __init__(self) -> None:
            self._managed = {"codex": Path("/managed/codex"), "gemini": None}

        def supported_engines(self):
            return ["codex", "gemini", "iflow", "opencode"]

        def resolve_bootstrap_targets(self, engine_spec=None):
            assert engine_spec is None
            return {
                "requested_engines": ["opencode", "codex"],
                "skipped_engines": ["gemini", "iflow"],
                "resolved_mode": "subset",
            }

        def resolve_managed_engine_command(self, engine: str):
            return self._managed.get(engine)

        def engine_package(self, engine: str) -> str:
            return f"{engine}-pkg"

        def install_package(self, package: str) -> CommandResult:  # noqa: ARG002
            return CommandResult(returncode=1, stdout="", stderr="token=abc fail")

        def resolve_engine_command(self, engine: str):  # noqa: ARG002
            return None

    report = module._ensure_with_diagnostics(FakeManager())
    assert report["summary"]["outcome"] == "partial_failure"
    assert report["summary"]["requested_engines"] == ["opencode", "codex"]
    assert report["summary"]["skipped_engines"] == ["gemini", "iflow"]
    assert report["summary"]["resolved_mode"] == "subset"
    assert report["summary"]["failed_engines"] == ["opencode"]
    assert report["opencode_warmup"]["attempted"] is False
    codex = report["engines"]["codex"]
    opencode = report["engines"]["opencode"]
    assert codex["outcome"] == "already_present"
    assert opencode["outcome"] == "install_failed"
    assert "abc" not in opencode["stderr_summary"]
    assert "token=***" in opencode["stderr_summary"]


def test_ensure_with_diagnostics_honors_explicit_engine_subset() -> None:
    module = _load_agent_manager_module()

    class FakeManager:
        def supported_engines(self):
            return ["codex", "gemini", "iflow", "opencode"]

        def resolve_bootstrap_targets(self, engine_spec=None):
            assert engine_spec == "gemini"
            return {
                "requested_engines": ["gemini"],
                "skipped_engines": ["codex", "iflow", "opencode"],
                "resolved_mode": "subset",
            }

        def resolve_managed_engine_command(self, engine: str):
            return None

        def engine_package(self, engine: str) -> str:
            return f"{engine}-pkg"

        def install_package(self, package: str) -> CommandResult:
            return CommandResult(returncode=1, stdout="", stderr=f"{package} token=abc fail")

        def resolve_engine_command(self, engine: str):  # noqa: ARG002
            return None

    report = module._ensure_with_diagnostics(FakeManager(), "gemini")
    assert report["summary"]["requested_engines"] == ["gemini"]
    assert report["summary"]["skipped_engines"] == ["codex", "iflow", "opencode"]
    assert report["summary"]["resolved_mode"] == "subset"
    assert report["summary"]["failed_engines"] == ["gemini"]
    gemini = report["engines"]["gemini"]
    assert gemini["outcome"] == "install_failed"
    assert "abc" not in gemini["stderr_summary"]
    assert "token=***" in gemini["stderr_summary"]


def test_ensure_with_diagnostics_opencode_warmup_failure_is_warning_only(monkeypatch) -> None:
    module = _load_agent_manager_module()

    class FakeManager:
        def __init__(self) -> None:
            self.profile = SimpleNamespace(build_subprocess_env=lambda: {})

        def supported_engines(self):
            return ["opencode"]

        def resolve_bootstrap_targets(self, engine_spec=None):
            assert engine_spec is None
            return {
                "requested_engines": ["opencode"],
                "skipped_engines": [],
                "resolved_mode": "subset",
            }

        def resolve_managed_engine_command(self, engine: str):  # noqa: ARG002
            return Path("/managed/opencode")

        def engine_package(self, engine: str) -> str:  # noqa: ARG002
            return "opencode-pkg"

        def install_package(self, package: str) -> CommandResult:  # noqa: ARG002
            return CommandResult(returncode=0, stdout="", stderr="")

        def resolve_engine_command(self, engine: str):  # noqa: ARG002
            return Path("/managed/opencode")

    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(  # noqa: ARG005
            returncode=1,
            stdout="",
            stderr="warmup failed",
        ),
    )

    report = module._ensure_with_diagnostics(FakeManager())
    assert report["summary"]["outcome"] == "ok"
    warmup = report["opencode_warmup"]
    assert warmup["attempted"] is True
    assert warmup["outcome"] == "failed"
    assert warmup["returncode"] == 1
    assert "warmup failed" in warmup["stderr_summary"]
