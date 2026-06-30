from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from server.config import config
from server.config_registry import keys
from server.services.engine_management.runtime_profile import RuntimeProfile, get_runtime_profile
from server.services.engine_management.zotero_bridge_cli_bundle import (
    ZoteroBridgeBundleError,
    ensure_zotero_bridge_managed_plugin,
    managed_bundle_store_root,
    managed_bundle_versions_root,
    read_zotero_bridge_bundle_state,
    validate_zotero_bridge_bundle_root,
    write_managed_bundle_current,
    write_zotero_bridge_bundle_state,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ZoteroBridgeBundleAutoUpdateConfig:
    enabled: bool
    repository: str
    branch: str
    interval_sec: int
    startup_delay_sec: int
    timeout_sec: int


class ZoteroBridgeBundleAutoUpdateManager:
    def __init__(self, profile: RuntimeProfile | None = None) -> None:
        self.profile = profile or get_runtime_profile()
        self._task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()

    def load_config(self) -> ZoteroBridgeBundleAutoUpdateConfig:
        raw = config.SYSTEM.ZOTERO_BRIDGE_BUNDLE_AUTO_UPDATE
        return ZoteroBridgeBundleAutoUpdateConfig(
            enabled=bool(raw.ENABLED),
            repository=str(raw.SOURCE_REPOSITORY),
            branch=str(raw.SOURCE_BRANCH),
            interval_sec=max(1, int(raw.INTERVAL_SEC)),
            startup_delay_sec=max(0, int(raw.STARTUP_DELAY_SEC)),
            timeout_sec=max(1, int(raw.TIMEOUT_SEC)),
        )

    def start(self) -> None:
        cfg = self.load_config()
        if not cfg.enabled:
            logger.info("Zotero Bridge bundle auto-update disabled")
            return
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        task = self._task
        if task is None:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None

    async def check_once(self) -> dict[str, Any]:
        async with self._lock:
            cfg = self.load_config()
            if not cfg.enabled:
                state = read_zotero_bridge_bundle_state(self.profile)
                state["status"] = "disabled"
                return state
            return await asyncio.to_thread(self._check_once_sync, cfg)

    async def _run_loop(self) -> None:
        try:
            cfg = self.load_config()
            if cfg.startup_delay_sec:
                await asyncio.sleep(cfg.startup_delay_sec)
            while True:
                try:
                    await self.check_once()
                except asyncio.CancelledError:
                    raise
                except (OSError, RuntimeError, ValueError, TypeError):
                    logger.warning(
                        "Zotero Bridge bundle auto-update check failed",
                        exc_info=True,
                    )
                cfg = self.load_config()
                await asyncio.sleep(cfg.interval_sec)
        except asyncio.CancelledError:
            raise

    def _check_once_sync(self, cfg: ZoteroBridgeBundleAutoUpdateConfig) -> dict[str, Any]:
        started_at = _utc_now_iso()
        previous_state = read_zotero_bridge_bundle_state(self.profile)
        checking_state = {
            **previous_state,
            "status": "checking",
            "source_repository": cfg.repository,
            "source_branch": cfg.branch,
            "checked_at": started_at,
        }
        write_zotero_bridge_bundle_state(self.profile, checking_state)

        try:
            remote_commit = self._remote_head(cfg)
            active_commit = previous_state.get("active_commit")
            if active_commit == remote_commit:
                state = {
                    **previous_state,
                    "status": "up_to_date",
                    "source_repository": cfg.repository,
                    "source_branch": cfg.branch,
                    "checked_at": _utc_now_iso(),
                    "remote_commit": remote_commit,
                    "error_code": None,
                    "error_message": None,
                }
                write_zotero_bridge_bundle_state(self.profile, state)
                return state

            bundle_root = self._ensure_version_dir(cfg, remote_commit)
            validate_zotero_bridge_bundle_root(bundle_root)
            ensure_zotero_bridge_managed_plugin(
                self.profile,
                engines=tuple(keys.ENGINE_KEYS),
                bundle_root=bundle_root,
            )
            write_managed_bundle_current(
                self.profile,
                active_commit=remote_commit,
                active_bundle_root=bundle_root,
            )
            state = {
                "status": "installed",
                "active_commit": remote_commit,
                "active_bundle_root": str(bundle_root),
                "source_repository": cfg.repository,
                "source_branch": cfg.branch,
                "checked_at": _utc_now_iso(),
                "installed_at": _utc_now_iso(),
                "remote_commit": remote_commit,
                "error_code": None,
                "error_message": None,
            }
            write_zotero_bridge_bundle_state(self.profile, state)
            return state
        except (OSError, RuntimeError, ValueError, TypeError, subprocess.SubprocessError) as exc:
            state = {
                **previous_state,
                "status": "failed",
                "source_repository": cfg.repository,
                "source_branch": cfg.branch,
                "checked_at": _utc_now_iso(),
                "error_code": type(exc).__name__,
                "error_message": str(exc),
            }
            write_zotero_bridge_bundle_state(self.profile, state)
            logger.warning(
                "Zotero Bridge bundle auto-update failed; keeping previous bundle",
                extra={
                    "component": "engine_management.zotero_bridge_bundle_auto_update",
                    "action": "check_once",
                    "error_type": type(exc).__name__,
                },
                exc_info=True,
            )
            return state

    def _remote_head(self, cfg: ZoteroBridgeBundleAutoUpdateConfig) -> str:
        proc = self._run_git(
            [
                "ls-remote",
                cfg.repository,
                f"refs/heads/{cfg.branch}",
            ],
            timeout=cfg.timeout_sec,
        )
        first_line = (proc.stdout or "").strip().splitlines()[0:1]
        if not first_line:
            raise RuntimeError(f"Remote branch not found: {cfg.repository} {cfg.branch}")
        commit = first_line[0].split()[0].strip()
        if len(commit) < 7:
            raise RuntimeError(f"Remote branch returned invalid commit: {commit}")
        return commit

    def _ensure_version_dir(
        self,
        cfg: ZoteroBridgeBundleAutoUpdateConfig,
        commit: str,
    ) -> Path:
        store_root = managed_bundle_store_root(self.profile)
        versions_root = managed_bundle_versions_root(self.profile)
        staging_root = store_root / "staging"
        version_dir = versions_root / commit
        if version_dir.exists():
            validate_zotero_bridge_bundle_root(version_dir)
            return version_dir

        staging_dir = staging_root / f"{commit}.tmp"
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
        staging_dir.parent.mkdir(parents=True, exist_ok=True)
        versions_root.mkdir(parents=True, exist_ok=True)

        self._run_git(
            [
                "clone",
                "--depth",
                "1",
                "--single-branch",
                "--branch",
                cfg.branch,
                cfg.repository,
                str(staging_dir),
            ],
            timeout=cfg.timeout_sec,
        )
        resolved_commit = self._run_git(
            ["-C", str(staging_dir), "rev-parse", "HEAD"],
            timeout=cfg.timeout_sec,
        ).stdout.strip()
        if resolved_commit != commit:
            raise RuntimeError(
                f"Fetched branch commit changed during update: expected {commit}, got {resolved_commit}"
            )

        git_dir = staging_dir / ".git"
        if git_dir.exists():
            shutil.rmtree(git_dir)
        validate_zotero_bridge_bundle_root(staging_dir)
        try:
            staging_dir.replace(version_dir)
        except OSError:
            if version_dir.exists():
                shutil.rmtree(staging_dir)
            else:
                raise
        return version_dir

    @staticmethod
    def _run_git(args: Iterable[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
        cmd = ["git", *args]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        if proc.returncode != 0:
            stderr = (proc.stderr or "").strip()
            raise RuntimeError(f"git command failed ({proc.returncode}): {' '.join(cmd)} {stderr}")
        return proc


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


zotero_bridge_bundle_auto_update_manager = ZoteroBridgeBundleAutoUpdateManager()
