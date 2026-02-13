import json
import logging
import os
import threading
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Dict, Iterable

import tomlkit

from ..config import config
from .runtime_profile import get_runtime_profile

logger = logging.getLogger(__name__)


class RunFolderTrustManager:
    """Manage per-run trust entries for Codex and Gemini global config files."""

    def __init__(
        self,
        codex_config_path: Path | None = None,
        gemini_trusted_path: Path | None = None,
        runs_root: Path | None = None,
    ) -> None:
        profile = get_runtime_profile()
        self.codex_config_path = codex_config_path or (profile.agent_home / ".codex" / "config.toml")
        self.gemini_trusted_path = gemini_trusted_path or (
            profile.agent_home / ".gemini" / "trustedFolders.json"
        )
        self.runs_root = (runs_root or Path(config.SYSTEM.RUNS_DIR)).resolve()
        self._thread_locks: Dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    def register_run_folder(self, engine: str, run_dir: Path) -> None:
        normalized = self._normalize_path(run_dir)
        if engine == "codex":
            self._set_codex_trust(normalized)
        elif engine == "gemini":
            self._set_gemini_trust(normalized)
        else:
            # iFlow currently has no trusted-folder mechanism.
            return

    def remove_run_folder(self, engine: str, run_dir: Path) -> None:
        normalized = self._normalize_path(run_dir)
        if engine == "codex":
            self._remove_codex_trust(normalized)
        elif engine == "gemini":
            self._remove_gemini_trust(normalized)
        else:
            return

    def bootstrap_parent_trust(self, runs_parent: Path) -> None:
        normalized = self._normalize_path(runs_parent)
        self._set_codex_trust(normalized)
        self._set_gemini_trust(normalized)

    def cleanup_stale_entries(self, active_run_dirs: Iterable[Path]) -> None:
        active = {self._normalize_path(path) for path in active_run_dirs}
        self._cleanup_codex_stale(active)
        self._cleanup_gemini_stale(active)

    def _normalize_path(self, path: Path) -> str:
        return str(path.resolve())

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

    def _set_codex_trust(self, normalized_path: str) -> None:
        self.codex_config_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.codex_config_path.exists():
            self.codex_config_path.write_text("", encoding="utf-8")
        with self._locked_file(self.codex_config_path):
            doc = self._load_toml(self.codex_config_path)
            projects = doc.get("projects")
            if not isinstance(projects, dict):
                projects = tomlkit.table()
                doc["projects"] = projects
            existing = projects.get(normalized_path)
            if not isinstance(existing, dict):
                existing = tomlkit.table()
                projects[normalized_path] = existing
            existing["trust_level"] = "trusted"
            self._write_toml(self.codex_config_path, doc)

    def _remove_codex_trust(self, normalized_path: str) -> None:
        if not self.codex_config_path.exists():
            return
        with self._locked_file(self.codex_config_path):
            doc = self._load_toml(self.codex_config_path)
            projects = doc.get("projects")
            if isinstance(projects, dict) and normalized_path in projects:
                del projects[normalized_path]
                self._write_toml(self.codex_config_path, doc)

    def _cleanup_codex_stale(self, active: set[str]) -> None:
        if not self.codex_config_path.exists():
            return
        with self._locked_file(self.codex_config_path):
            doc = self._load_toml(self.codex_config_path)
            projects = doc.get("projects")
            if not isinstance(projects, dict):
                return
            stale = [
                key
                for key in list(projects.keys())
                if isinstance(key, str) and self._is_run_child_path(key) and key not in active
            ]
            if not stale:
                return
            for key in stale:
                del projects[key]
            self._write_toml(self.codex_config_path, doc)

    def _set_gemini_trust(self, normalized_path: str) -> None:
        self.gemini_trusted_path.parent.mkdir(parents=True, exist_ok=True)
        with self._locked_file(self.gemini_trusted_path):
            payload = self._load_or_repair_trusted_folders_unlocked()
            payload[normalized_path] = "TRUST_FOLDER"
            self._write_json_atomically(self.gemini_trusted_path, payload)

    def _remove_gemini_trust(self, normalized_path: str) -> None:
        if not self.gemini_trusted_path.exists():
            return
        with self._locked_file(self.gemini_trusted_path):
            payload = self._load_or_repair_trusted_folders_unlocked()
            if normalized_path in payload:
                del payload[normalized_path]
                self._write_json_atomically(self.gemini_trusted_path, payload)

    def _cleanup_gemini_stale(self, active: set[str]) -> None:
        if not self.gemini_trusted_path.exists():
            return
        with self._locked_file(self.gemini_trusted_path):
            payload = self._load_or_repair_trusted_folders_unlocked()
            stale = [
                key
                for key in list(payload.keys())
                if self._is_run_child_path(key) and key not in active
            ]
            if not stale:
                return
            for key in stale:
                del payload[key]
            self._write_json_atomically(self.gemini_trusted_path, payload)

    def _load_or_repair_trusted_folders_unlocked(self) -> Dict[str, str]:
        self.gemini_trusted_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.gemini_trusted_path.exists():
            self._write_json_atomically(self.gemini_trusted_path, {})
            return {}
        try:
            raw = self.gemini_trusted_path.read_text(encoding="utf-8")
            loaded = json.loads(raw)
            if not isinstance(loaded, dict):
                raise ValueError("trustedFolders.json must be an object")
            return {str(k): str(v) for k, v in loaded.items()}
        except Exception:
            self._backup_file(self.gemini_trusted_path)
            self._write_json_atomically(self.gemini_trusted_path, {})
            return {}

    def _load_toml(self, path: Path) -> tomlkit.TOMLDocument:
        try:
            return tomlkit.parse(path.read_text(encoding="utf-8"))
        except Exception:
            self._backup_file(path)
            return tomlkit.document()

    def _write_toml(self, path: Path, doc: tomlkit.TOMLDocument) -> None:
        content = tomlkit.dumps(doc)
        self._write_text_atomically(path, content)

    def _write_json_atomically(self, path: Path, payload: Dict[str, str]) -> None:
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
            logger.warning("Failed to backup malformed trust config: %s", path, exc_info=True)

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
                # Keep thread lock as fallback on platforms without fcntl.
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


run_folder_trust_manager = RunFolderTrustManager()
