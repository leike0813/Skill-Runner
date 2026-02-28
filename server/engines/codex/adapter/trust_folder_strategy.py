from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile

import tomlkit


class CodexTrustFolderStrategy:
    def __init__(self, config_path: Path, runs_root: Path) -> None:
        self.config_path = config_path
        self.runs_root = runs_root.resolve()
        self._thread_locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    def register(self, normalized_path: str) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.config_path.exists():
            self.config_path.write_text("", encoding="utf-8")
        with self._locked_file(self.config_path):
            doc = self._load_toml(self.config_path)
            projects = doc.get("projects")
            if not isinstance(projects, dict):
                projects = tomlkit.table()
                doc["projects"] = projects
            existing = projects.get(normalized_path)
            if not isinstance(existing, dict):
                existing = tomlkit.table()
                projects[normalized_path] = existing
            existing["trust_level"] = "trusted"
            self._write_toml(self.config_path, doc)

    def remove(self, normalized_path: str) -> None:
        if not self.config_path.exists():
            return
        with self._locked_file(self.config_path):
            doc = self._load_toml(self.config_path)
            projects = doc.get("projects")
            if isinstance(projects, dict) and normalized_path in projects:
                del projects[normalized_path]
                self._write_toml(self.config_path, doc)

    def bootstrap_parent_trust(self, normalized_parent_path: str) -> None:
        self.register(normalized_parent_path)

    def cleanup_stale(self, active_normalized_paths: set[str]) -> None:
        if not self.config_path.exists():
            return
        with self._locked_file(self.config_path):
            doc = self._load_toml(self.config_path)
            projects = doc.get("projects")
            if not isinstance(projects, dict):
                return
            stale = [
                key
                for key in list(projects.keys())
                if isinstance(key, str) and self._is_run_child_path(key) and key not in active_normalized_paths
            ]
            if not stale:
                return
            for key in stale:
                del projects[key]
            self._write_toml(self.config_path, doc)

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

    def _load_toml(self, path: Path) -> tomlkit.TOMLDocument:
        try:
            return tomlkit.parse(path.read_text(encoding="utf-8"))
        except Exception:
            return tomlkit.document()

    def _write_toml(self, path: Path, doc: tomlkit.TOMLDocument) -> None:
        content = tomlkit.dumps(doc)
        self._write_text_atomically(path, content)

    def _write_text_atomically(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile("w", delete=False, dir=str(path.parent), encoding="utf-8") as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)
        os.replace(tmp_path, path)

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
