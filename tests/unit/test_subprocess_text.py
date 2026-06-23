from __future__ import annotations

from types import SimpleNamespace

from server.services.platform import subprocess_text


def test_run_text_forces_utf8_replace(monkeypatch):
    captured: dict[str, object] = {}

    def _fake_run(args, **kwargs):  # type: ignore[no-untyped-def]
        captured["args"] = list(args)
        captured.update(kwargs)
        return SimpleNamespace(returncode=0, stdout="smart quote “中文”", stderr="")

    monkeypatch.setattr(subprocess_text.subprocess, "run", _fake_run)

    result = subprocess_text.run_text(["tool", "--version"], env={"A": "B"})

    assert result.stdout == "smart quote “中文”"
    assert captured["args"] == ["tool", "--version"]
    assert captured["text"] is True
    assert captured["encoding"] == "utf-8"
    assert captured["errors"] == "replace"
    assert captured["capture_output"] is True
    assert captured["check"] is False
