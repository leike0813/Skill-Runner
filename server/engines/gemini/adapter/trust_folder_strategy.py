from __future__ import annotations

import json
import os
import threading
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile


class GeminiTrustFolderStrategy:
    def __init__(self, trusted_folders_path: Path, runs_root: Path) -> None:
        self.trusted_folders_path = trusted_folders_path
        self.runs_root = runs_root.resolve()
        self._thread_locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    def register(self, normalized_path: str) -> None:
        self.trusted_folders_path.parent.mkdir(parents=True, exist_ok=True)
        with self._locked_file(self.trusted_folders_path):
            payload = self._load_or_repair_trusted_folders_unlocked()
            payload[normalized_path] = "TRUST_FOLDER"
            self._write_json_atomically(self.trusted_folders_path, payload)

    def remove(self, normalized_path: str) -> None:
        if not self.trusted_folders_path.exists():
            return
        with self._locked_file(self.trusted_folders_path):
            payload = self._load_or_repair_trusted_folders_unlocked()
            if normalized_path in payload:
                del payload[normalized_path]
                self._write_json_atomically(self.trusted_folders_path, payload)

    def bootstrap_parent_trust(self, normalized_parent_path: str) -> None:
        self.register(normalized_parent_path)

    def cleanup_stale(self, active_normalized_paths: set[str]) -> None:
        if not self.trusted_folders_path.exists():
            return
        with self._locked_file(self.trusted_folders_path):
            payload = self._load_or_repair_trusted_folders_unlocked()
            stale = [
                key
                for key in list(payload.keys())
                if self._is_run_child_path(key) and key not in active_normalized_paths
            ]
            if not stale:
                return
            for key in stale:
                del payload[key]
            self._write_json_atomically(self.trusted_folders_path, payload)

    def _is_run_child_path(self, raw_path: str) -> bool:
        try:
            candidate = Path(raw_path).resolve()
        except Exception:
            return False
        if candidate == self.runs_root:
            return False
        try:
            candidate.relative_to(self.runs_root)
            return True
        except ValueError:
            return False

    def _load_or_repair_trusted_folders_unlocked(self) -> dict[str, str]:
        self.trusted_folders_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.trusted_folders_path.exists():
            self._write_json_atomically(self.trusted_folders_path, {})
            return {}
        try:
            raw = self.trusted_folders_path.read_text(encoding="utf-8")
            loaded = json.loads(raw)
            if not isinstance(loaded, dict):
                raise ValueError("trustedFolders.json must be an object")
            return {str(k): str(v) for k, v in loaded.items()}
        except Exception:
            self._backup_file(self.trusted_folders_path)
            self._write_json_atomically(self.trusted_folders_path, {})
            return {}

    def _write_json_atomically(self, path: Path, payload: dict[str, str]) -> None:
        content = json.dumps(payload, indent=2, sort_keys=True)
        self._write_text_atomically(path, content + "\n")

    def _write_text_atomically(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile("w", delete=False, dir=str(path.parent), encoding="utf-8") as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)
        os.replace(tmp_path, path)

    def _backup_file(self, path: Path) -> None:
        if not path.exists():
            return
        backup = path.with_name(f"{path.name}.bak")
        try:
            backup.write_bytes(path.read_bytes())
        except Exception:
            pass

    def _get_thread_lock(self, target: Path) -> threading.Lock:
        key = str(target)
        with self._locks_guard:
            if key not in self._thread_locks:
                self._thread_locks[key] = threading.Lock()
            return self._thread_locks[key]

    @contextmanager
    def _locked_file(self, target: Path):
        thread_lock = self._get_thread_lock(target)
        thread_lock.acquire()
        lock_path = target.with_name(f"{target.name}.lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with open(lock_path, "a+", encoding="utf-8") as lock_file:
            try:
                import fcntl

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            except Exception:
                pass
            try:
                yield
            finally:
                try:
                    import fcntl

                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                except Exception:
                    pass
                thread_lock.release()
