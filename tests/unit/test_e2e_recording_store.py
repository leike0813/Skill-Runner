from __future__ import annotations

import json
from pathlib import Path

from e2e_client.recording import RecordingStore


def _write_recording(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_list_recordings_sorted_by_created_at_desc(tmp_path: Path):
    store = RecordingStore(tmp_path / "recordings")
    recordings_dir = tmp_path / "recordings"

    _write_recording(
        recordings_dir / "req-old.json",
        {
            "request_id": "req-old",
            "created_at": "2026-02-20T08:00:00+00:00",
            "updated_at": "2026-02-20T08:10:00+00:00",
            "run_source": "installed",
            "steps": [],
        },
    )
    _write_recording(
        recordings_dir / "req-new.json",
        {
            "request_id": "req-new",
            "created_at": "2026-02-22T09:00:00+00:00",
            "updated_at": "2026-02-22T09:01:00+00:00",
            "run_source": "temp",
            "steps": [],
        },
    )
    _write_recording(
        recordings_dir / "req-mid.json",
        {
            "request_id": "req-mid",
            "created_at": "2026-02-21T12:00:00+00:00",
            "updated_at": "2026-02-21T12:05:00+00:00",
            "run_source": "installed",
            "steps": [],
        },
    )

    rows = store.list_recordings()
    assert [row["request_id"] for row in rows] == ["req-new", "req-mid", "req-old"]
    assert rows[0]["created_at"] == "2026-02-22T09:00:00+00:00"


def test_list_recordings_fallback_to_updated_at_when_created_at_missing(tmp_path: Path):
    store = RecordingStore(tmp_path / "recordings")
    recordings_dir = tmp_path / "recordings"

    _write_recording(
        recordings_dir / "req-no-created-newer.json",
        {
            "request_id": "req-no-created-newer",
            "updated_at": "2026-02-22T10:00:00+00:00",
            "run_source": "installed",
            "steps": [],
        },
    )
    _write_recording(
        recordings_dir / "req-no-created-older.json",
        {
            "request_id": "req-no-created-older",
            "updated_at": "2026-02-22T09:00:00+00:00",
            "run_source": "installed",
            "steps": [],
        },
    )

    rows = store.list_recordings()
    assert [row["request_id"] for row in rows] == [
        "req-no-created-newer",
        "req-no-created-older",
    ]
