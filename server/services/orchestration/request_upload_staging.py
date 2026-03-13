import io
import json
import zipfile
from pathlib import Path
from shutil import move, rmtree
from typing import Any

from server.services.platform.cache_key_builder import build_input_manifest


def ensure_request_root(base_dir: str | Path, request_id: str, request_payload: dict[str, Any] | None = None) -> Path:
    request_dir = Path(base_dir) / request_id
    request_dir.mkdir(parents=True, exist_ok=True)
    (request_dir / "uploads").mkdir(exist_ok=True)
    if request_payload is not None:
        (request_dir / "request.json").write_text(
            json.dumps(request_payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    return request_dir


def get_request_root(base_dir: str | Path, request_id: str) -> Path | None:
    path = Path(base_dir) / request_id
    return path if path.exists() else None


def handle_upload(base_dir: str | Path, request_id: str, file_bytes: bytes) -> dict[str, Any]:
    request_dir = get_request_root(base_dir, request_id)
    if request_dir is None:
        raise ValueError(f"Request {request_id} not found")
    uploads_dir = request_dir / "uploads"
    uploads_dir.mkdir(exist_ok=True)
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as zipped:
            zipped.extractall(uploads_dir)
    except zipfile.BadZipFile as exc:
        raise ValueError("Invalid zip file") from exc
    extracted_files = [
        path.relative_to(uploads_dir).as_posix()
        for path in uploads_dir.rglob("*")
        if path.is_file()
    ]
    return {"status": "success", "extracted_files": extracted_files}


def write_input_manifest(base_dir: str | Path, request_id: str) -> Path:
    request_dir = get_request_root(base_dir, request_id)
    if request_dir is None:
        raise ValueError(f"Request {request_id} not found")
    uploads_dir = request_dir / "uploads"
    manifest = build_input_manifest(uploads_dir)
    manifest_path = request_dir / "input_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return manifest_path


def promote_request_uploads(base_dir: str | Path, request_id: str, run_dir: str | Path) -> None:
    request_dir = get_request_root(base_dir, request_id)
    if request_dir is None:
        raise ValueError(f"Request {request_id} not found")
    run_root = Path(run_dir)
    if not run_root.exists():
        raise ValueError(f"Run directory {run_root} not found")
    source_dir = request_dir / "uploads"
    target_dir = run_root / "uploads"
    if target_dir.exists():
        raise ValueError(f"Run uploads already exist for {run_root.name}")
    if source_dir.exists():
        move(str(source_dir), str(target_dir))


def delete_request_root(base_dir: str | Path, request_id: str) -> None:
    request_dir = get_request_root(base_dir, request_id)
    if request_dir is not None and request_dir.exists():
        rmtree(request_dir, ignore_errors=True)


def purge_request_roots(base_dir: str | Path) -> None:
    root = Path(base_dir)
    root.mkdir(parents=True, exist_ok=True)
    for entry in root.iterdir():
        if entry.is_dir():
            rmtree(entry, ignore_errors=True)
        else:
            entry.unlink(missing_ok=True)
