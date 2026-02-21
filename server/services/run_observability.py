import json
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from .run_store import run_store
from .workspace_manager import workspace_manager
from .skill_browser import (
    PREVIEW_MAX_BYTES,
    list_skill_entries,
    resolve_skill_file_path,
)


RUNNING_STATUSES = {"queued", "running"}
RUN_PREVIEW_BINARY_SAMPLE_BYTES = 4096
RUN_PREVIEW_CONTROL_RATIO_THRESHOLD = 0.30


class RunObservabilityService:
    def list_runs(self, limit: int = 200) -> List[Dict[str, Any]]:
        rows = run_store.list_requests_with_runs(limit=limit)
        results: List[Dict[str, Any]] = []
        for row in rows:
            run_id_obj = row.get("run_id")
            if not isinstance(run_id_obj, str) or not run_id_obj:
                continue
            run_id = run_id_obj
            run_dir = workspace_manager.get_run_dir(run_id)
            status_payload = self._read_status_payload(run_dir) if run_dir else {}
            run_status = self._normalize_run_status(row, status_payload)
            file_state = self._build_file_state(run_dir)
            updated_at = status_payload.get("updated_at")
            if not isinstance(updated_at, str):
                updated_at = self._derive_updated_at(run_dir, row)
            results.append(
                {
                    "request_id": row.get("request_id"),
                    "run_id": run_id,
                    "skill_id": row.get("skill_id"),
                    "engine": row.get("engine"),
                    "status": run_status,
                    "updated_at": updated_at,
                    "file_state": file_state,
                }
            )
        return results

    def get_run_detail(self, request_id: str) -> Dict[str, Any]:
        record = run_store.get_request_with_run(request_id)
        if not record:
            raise ValueError("Request not found")
        run_id_obj = record.get("run_id")
        if not isinstance(run_id_obj, str) or not run_id_obj:
            raise ValueError("Run not found")
        run_dir = workspace_manager.get_run_dir(run_id_obj)
        if not run_dir or not run_dir.exists():
            raise FileNotFoundError("Run directory not found")

        status_payload = self._read_status_payload(run_dir)
        run_status = self._normalize_run_status(record, status_payload)
        file_state = self._build_file_state(run_dir)
        entries = list_skill_entries(run_dir)

        return {
            "request_id": request_id,
            "run_id": run_id_obj,
            "run_dir": str(run_dir),
            "skill_id": record.get("skill_id"),
            "engine": record.get("engine"),
            "status": run_status,
            "updated_at": status_payload.get("updated_at") or self._derive_updated_at(run_dir, record),
            "entries": entries,
            "file_state": file_state,
            "poll_logs": run_status in RUNNING_STATUSES,
        }

    def resolve_run_file_path(self, request_id: str, relative_path: str) -> Path:
        detail = self.get_run_detail(request_id)
        run_dir = Path(detail["run_dir"])
        return resolve_skill_file_path(run_dir, relative_path)

    def build_run_file_preview(self, request_id: str, relative_path: str) -> Dict[str, Any]:
        file_path = self.resolve_run_file_path(request_id, relative_path)
        return self._build_run_preview_payload(file_path)

    def get_logs_tail(self, request_id: str, max_bytes: int = 64 * 1024) -> Dict[str, Any]:
        detail = self.get_run_detail(request_id)
        run_dir = Path(detail["run_dir"])
        logs_dir = run_dir / "logs"
        stdout_path = logs_dir / "stdout.txt"
        stderr_path = logs_dir / "stderr.txt"
        return {
            "request_id": request_id,
            "run_id": detail["run_id"],
            "status": detail["status"],
            "poll": detail["status"] in RUNNING_STATUSES,
            "stdout": self._tail_file(stdout_path, max_bytes=max_bytes),
            "stderr": self._tail_file(stderr_path, max_bytes=max_bytes),
        }

    def _read_status_payload(self, run_dir: Path) -> Dict[str, Any]:
        status_file = run_dir / "status.json"
        if not status_file.exists():
            return {}
        try:
            with open(status_file, "r", encoding="utf-8") as f:
                payload = json.load(f)
            if isinstance(payload, dict):
                return payload
            return {}
        except Exception:
            return {}

    def _normalize_run_status(self, record: Dict[str, Any], status_payload: Dict[str, Any]) -> str:
        status_obj = status_payload.get("status")
        if isinstance(status_obj, str) and status_obj:
            return status_obj
        run_status_obj = record.get("run_status")
        if isinstance(run_status_obj, str) and run_status_obj:
            return run_status_obj
        return "queued"

    def _build_file_state(self, run_dir: Path | None) -> Dict[str, Dict[str, Any]]:
        if not run_dir:
            return {}
        targets = {
            "status": run_dir / "status.json",
            "input": run_dir / "input.json",
            "prompt": run_dir / "logs" / "prompt.txt",
            "stdout": run_dir / "logs" / "stdout.txt",
            "stderr": run_dir / "logs" / "stderr.txt",
            "result": run_dir / "result" / "result.json",
            "artifacts_dir": run_dir / "artifacts",
        }
        state: Dict[str, Dict[str, Any]] = {}
        for name, path in targets.items():
            exists = path.exists()
            item: Dict[str, Any] = {"exists": exists}
            if exists:
                stat = path.stat()
                item["size"] = stat.st_size
                item["mtime"] = datetime.fromtimestamp(stat.st_mtime).isoformat()
                item["is_dir"] = path.is_dir()
            state[name] = item
        return state

    def _derive_updated_at(self, run_dir: Path | None, record: Dict[str, Any]) -> str | None:
        if run_dir and run_dir.exists():
            try:
                mtime = run_dir.stat().st_mtime
                return datetime.fromtimestamp(mtime).isoformat()
            except Exception:
                pass
        request_created = record.get("request_created_at")
        return request_created if isinstance(request_created, str) else None

    def _tail_file(self, path: Path, max_bytes: int) -> str:
        if not path.exists() or not path.is_file():
            return ""
        with open(path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            read_size = min(size, max_bytes)
            if read_size <= 0:
                return ""
            f.seek(size - read_size)
            data = f.read(read_size)
        return data.decode("utf-8", errors="replace")

    def _build_run_preview_payload(self, file_path: Path) -> Dict[str, Any]:
        size = file_path.stat().st_size
        if size > PREVIEW_MAX_BYTES:
            return {
                "mode": "too_large",
                "content": None,
                "size": size,
                "meta": "无信息",
            }

        raw = file_path.read_bytes()
        if self._looks_binary(raw):
            return {
                "mode": "binary",
                "content": None,
                "size": size,
                "meta": "无信息",
            }

        text, encoding = self._decode_text_with_fallback(raw)
        if text is None or encoding is None:
            return {
                "mode": "binary",
                "content": None,
                "size": size,
                "meta": "无信息",
            }

        return {
            "mode": "text",
            "content": text,
            "size": size,
            "meta": f"{size} bytes, {encoding}",
        }

    def _looks_binary(self, data: bytes) -> bool:
        sample = data[:RUN_PREVIEW_BINARY_SAMPLE_BYTES]
        if not sample:
            return False
        if b"\x00" in sample:
            return True

        control_count = 0
        for byte in sample:
            if byte == 127 or (byte < 32 and byte not in (9, 10, 13)):
                control_count += 1
        return (control_count / len(sample)) > RUN_PREVIEW_CONTROL_RATIO_THRESHOLD

    def _decode_text_with_fallback(self, data: bytes) -> tuple[str | None, str | None]:
        if data.startswith(b"\xef\xbb\xbf"):
            try:
                return data.decode("utf-8-sig"), "utf-8-sig"
            except UnicodeDecodeError:
                pass

        for encoding in ("utf-8", "utf-8-sig"):
            try:
                return data.decode(encoding), encoding
            except UnicodeDecodeError:
                continue

        candidates: list[tuple[str, str, int, int]] = []
        for encoding in ("gb18030", "big5"):
            try:
                decoded = data.decode(encoding)
            except UnicodeDecodeError:
                continue
            score = self._score_decoded_text(decoded)
            candidates.append((encoding, decoded, score, len(candidates)))
        if not candidates:
            return None, None
        best = max(candidates, key=lambda item: (item[2], -item[3]))
        return best[1], best[0]

    def _score_decoded_text(self, text: str) -> int:
        score = 0
        for ch in text:
            cp = ord(ch)
            if ch in ("\t", "\n", "\r"):
                score += 1
                continue
            if ch == "\ufeff":
                score -= 2
                continue
            if 32 <= cp <= 126:
                score += 1
                continue
            if 0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF or 0xF900 <= cp <= 0xFAFF:
                score += 2
                continue
            category = unicodedata.category(ch)
            if category.startswith("C"):
                score -= 3
        return score


run_observability_service = RunObservabilityService()
