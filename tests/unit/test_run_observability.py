import json
from pathlib import Path

from server.services.run_observability import RunObservabilityService
from server.services.skill_browser import PREVIEW_MAX_BYTES


def _patch_request_lookup(monkeypatch, run_dir: Path) -> None:
    monkeypatch.setattr(
        "server.services.run_observability.run_store.get_request_with_run",
        lambda request_id: {
            "request_id": request_id,
            "run_id": "run-1",
            "skill_id": "demo",
            "engine": "gemini",
            "request_created_at": "2026-01-01T00:00:00",
            "run_status": "running",
        },
    )
    monkeypatch.setattr(
        "server.services.run_observability.workspace_manager.get_run_dir",
        lambda _run_id: run_dir,
    )


def test_list_runs_and_get_logs_tail(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-1"
    (run_dir / "logs").mkdir(parents=True, exist_ok=True)
    (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
    (run_dir / "logs" / "stdout.txt").write_text("line1\nline2\n", encoding="utf-8")
    (run_dir / "logs" / "stderr.txt").write_text("err1\n", encoding="utf-8")
    (run_dir / "status.json").write_text(json.dumps({"status": "running", "updated_at": "2026-01-01T00:00:00"}), encoding="utf-8")

    monkeypatch.setattr(
        "server.services.run_observability.run_store.list_requests_with_runs",
        lambda limit=200: [
            {
                "request_id": "req-1",
                "run_id": "run-1",
                "skill_id": "demo",
                "engine": "gemini",
                "request_created_at": "2026-01-01T00:00:00",
                "run_status": "running",
            }
        ],
    )
    monkeypatch.setattr(
        "server.services.run_observability.run_store.get_request_with_run",
        lambda request_id: {
            "request_id": request_id,
            "run_id": "run-1",
            "skill_id": "demo",
            "engine": "gemini",
            "request_created_at": "2026-01-01T00:00:00",
            "run_status": "running",
        },
    )
    monkeypatch.setattr(
        "server.services.run_observability.workspace_manager.get_run_dir",
        lambda _run_id: run_dir,
    )

    service = RunObservabilityService()
    rows = service.list_runs()
    assert len(rows) == 1
    assert rows[0]["request_id"] == "req-1"
    assert rows[0]["status"] == "running"

    tail = service.get_logs_tail("req-1", max_bytes=5)
    assert tail["poll"] is True
    assert tail["stdout"].endswith("ne2\n")
    assert "err1" in tail["stderr"]


def test_run_file_preview_encoding_fallback(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-1"
    run_dir.mkdir(parents=True, exist_ok=True)
    _patch_request_lookup(monkeypatch, run_dir)

    gb_file = run_dir / "gb.md"
    gb_file.write_bytes("中文内容".encode("gb18030"))

    big5_file = run_dir / "big5.md"
    big5_file.write_bytes("中文內容".encode("big5"))

    bom_file = run_dir / "bom.md"
    bom_file.write_bytes("带BOM".encode("utf-8-sig"))

    service = RunObservabilityService()

    gb_preview = service.build_run_file_preview("req-1", "gb.md")
    assert gb_preview["mode"] == "text"
    assert "中文内容" in gb_preview["content"]
    assert gb_preview["meta"].endswith("gb18030")

    big5_preview = service.build_run_file_preview("req-1", "big5.md")
    assert big5_preview["mode"] == "text"
    assert "中文內容" in big5_preview["content"]
    assert big5_preview["meta"].endswith("big5")

    bom_preview = service.build_run_file_preview("req-1", "bom.md")
    assert bom_preview["mode"] == "text"
    assert "带BOM" in bom_preview["content"]
    assert bom_preview["meta"].endswith("utf-8-sig")


def test_run_file_preview_binary_heuristic_and_large(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-1"
    run_dir.mkdir(parents=True, exist_ok=True)
    _patch_request_lookup(monkeypatch, run_dir)

    nul_file = run_dir / "nul.bin"
    nul_file.write_bytes(b"abc\x00def")

    control_file = run_dir / "ctrl.bin"
    control_file.write_bytes(bytes([1]) * 80 + b"normal-text")

    large_file = run_dir / "large.txt"
    large_file.write_text("x" * (PREVIEW_MAX_BYTES + 1), encoding="utf-8")

    service = RunObservabilityService()

    nul_preview = service.build_run_file_preview("req-1", "nul.bin")
    assert nul_preview["mode"] == "binary"

    control_preview = service.build_run_file_preview("req-1", "ctrl.bin")
    assert control_preview["mode"] == "binary"

    large_preview = service.build_run_file_preview("req-1", "large.txt")
    assert large_preview["mode"] == "too_large"
