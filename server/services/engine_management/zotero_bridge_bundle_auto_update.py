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
    ensure_zotero_bridge_managed_plugin,
    managed_bundle_store_root,
    managed_bundle_versions_root,
    read_zotero_bridge_bundle_state,
    validate_zotero_bridge_bundle_root,
    write_managed_bundle_current,
    write_zotero_bridge_bundle_state,
    zotero_bridge_bundle_status,
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


class ZoteroBridgeBundleUpdateError(RuntimeError):
    """Raised when a manual bundle update operation fails."""


class ZoteroBridgeBundleUpdateConflict(ZoteroBridgeBundleUpdateError):
    """Raised when no checked candidate can be installed safely."""


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
            return await asyncio.to_thread(self._check_and_install_sync, cfg)

    async def check_update(self) -> dict[str, Any]:
        """Check for an update without downloading or activating it."""
        async with self._lock:
            return await asyncio.to_thread(self._check_update_sync, self.load_config())

    async def install_update(self) -> dict[str, Any]:
        """Install the candidate recorded by the latest successful check."""
        async with self._lock:
            return await asyncio.to_thread(self._install_update_sync, self.load_config())

    def management_status(self) -> dict[str, Any]:
        """Return the stable, path-free status projection used by management APIs."""
        cfg = self.load_config()
        bundle = zotero_bridge_bundle_status(self.profile)
        state = bundle.get("state") if isinstance(bundle.get("state"), dict) else {}
        raw_status = str(state.get("status") or "idle")
        status = raw_status if raw_status in {
            "checking",
            "up_to_date",
            "update_available",
            "installing",
            "installed",
            "failed",
        } else "idle"
        error_code = _optional_string(state.get("error_code"))
        return {
            "plugin_id": "zotero-bridge-cli",
            "version": _optional_string(bundle.get("version")),
            "source": "managed" if bundle.get("source") == "managed" else "builtin",
            "current_commit": _optional_string(bundle.get("current_commit")),
            "auto_update_enabled": cfg.enabled,
            "update_status": status,
            "available_commit": _optional_string(state.get("available_commit")),
            "checked_at": _optional_string(state.get("checked_at")),
            "installed_at": _optional_string(state.get("installed_at")),
            "error_code": error_code,
            "error_message": (
                "Plugin update failed. Check the server logs for details."
                if error_code
                else None
            ),
        }

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

    def _check_and_install_sync(
        self,
        cfg: ZoteroBridgeBundleAutoUpdateConfig,
    ) -> dict[str, Any]:
        try:
            state = self._check_update_sync(cfg)
            if state.get("status") == "update_available":
                return self._install_update_sync(cfg)
            return state
        except ZoteroBridgeBundleUpdateError:
            return read_zotero_bridge_bundle_state(self.profile)

    def _check_update_sync(self, cfg: ZoteroBridgeBundleAutoUpdateConfig) -> dict[str, Any]:
        started_at = _utc_now_iso()
        previous_state = read_zotero_bridge_bundle_state(self.profile)
        checking_state = {
            **previous_state,
            "status": "checking",
            "source_repository": cfg.repository,
            "source_branch": cfg.branch,
            "checked_at": started_at,
            "available_commit": None,
        }
        write_zotero_bridge_bundle_state(self.profile, checking_state)

        try:
            remote_commit = self._remote_head(cfg)
            active_commit = zotero_bridge_bundle_status(self.profile).get("current_commit")
            if active_commit == remote_commit:
                state = {
                    **previous_state,
                    "status": "up_to_date",
                    "source_repository": cfg.repository,
                    "source_branch": cfg.branch,
                    "checked_at": _utc_now_iso(),
                    "remote_commit": remote_commit,
                    "available_commit": None,
                    "error_code": None,
                    "error_message": None,
                }
                write_zotero_bridge_bundle_state(self.profile, state)
                return state
            state = {
                **previous_state,
                "status": "update_available",
                "source_repository": cfg.repository,
                "source_branch": cfg.branch,
                "checked_at": _utc_now_iso(),
                "remote_commit": remote_commit,
                "available_commit": remote_commit,
                "error_code": None,
                "error_message": None,
            }
            write_zotero_bridge_bundle_state(self.profile, state)
            return state
        except (OSError, RuntimeError, ValueError, TypeError, subprocess.SubprocessError) as exc:
            self._record_failure(previous_state, cfg, exc, action="check_update", clear_candidate=True)
            raise ZoteroBridgeBundleUpdateError("Zotero Bridge bundle update check failed") from exc

    def _install_update_sync(self, cfg: ZoteroBridgeBundleAutoUpdateConfig) -> dict[str, Any]:
        previous_state = read_zotero_bridge_bundle_state(self.profile)
        candidate = previous_state.get("available_commit")
        if not isinstance(candidate, str) or not candidate:
            raise ZoteroBridgeBundleUpdateConflict("No checked plugin update is available")

        installing_state = {
            **previous_state,
            "status": "installing",
            "error_code": None,
            "error_message": None,
        }
        write_zotero_bridge_bundle_state(self.profile, installing_state)
        try:
            remote_commit = self._remote_head(cfg)
            if remote_commit != candidate:
                conflict = ZoteroBridgeBundleUpdateConflict(
                    "The checked plugin update changed; check for updates again"
                )
                self._record_failure(
                    previous_state,
                    cfg,
                    conflict,
                    action="install_update",
                    clear_candidate=True,
                )
                raise conflict

            active_commit = zotero_bridge_bundle_status(self.profile).get("current_commit")
            if active_commit == candidate:
                state = {
                    **previous_state,
                    "status": "installed",
                    "active_commit": candidate,
                    "checked_at": previous_state.get("checked_at") or _utc_now_iso(),
                    "installed_at": previous_state.get("installed_at") or _utc_now_iso(),
                    "remote_commit": candidate,
                    "available_commit": None,
                    "error_code": None,
                    "error_message": None,
                }
                write_zotero_bridge_bundle_state(self.profile, state)
                return state

            bundle_root = self._ensure_version_dir(cfg, candidate)
            validate_zotero_bridge_bundle_root(bundle_root)
            ensure_zotero_bridge_managed_plugin(
                self.profile,
                engines=tuple(keys.ENGINE_KEYS),
                bundle_root=bundle_root,
            )
            write_managed_bundle_current(
                self.profile,
                active_commit=candidate,
                active_bundle_root=bundle_root,
            )
            state = {
                "status": "installed",
                "active_commit": candidate,
                "active_bundle_root": str(bundle_root),
                "source_repository": cfg.repository,
                "source_branch": cfg.branch,
                "checked_at": previous_state.get("checked_at") or _utc_now_iso(),
                "installed_at": _utc_now_iso(),
                "remote_commit": candidate,
                "available_commit": None,
                "error_code": None,
                "error_message": None,
            }
            write_zotero_bridge_bundle_state(self.profile, state)
            return state
        except ZoteroBridgeBundleUpdateConflict:
            raise
        except (OSError, RuntimeError, ValueError, TypeError, subprocess.SubprocessError) as exc:
            self._record_failure(
                previous_state,
                cfg,
                exc,
                action="install_update",
                clear_candidate=False,
            )
            raise ZoteroBridgeBundleUpdateError("Zotero Bridge bundle update installation failed") from exc

    def _record_failure(
        self,
        previous_state: dict[str, Any],
        cfg: ZoteroBridgeBundleAutoUpdateConfig,
        exc: BaseException,
        *,
        action: str,
        clear_candidate: bool,
    ) -> None:
        state = {
            **previous_state,
            "status": "failed",
            "source_repository": cfg.repository,
            "source_branch": cfg.branch,
            "checked_at": _utc_now_iso(),
            "error_code": type(exc).__name__,
            "error_message": str(exc),
        }
        if clear_candidate:
            state["available_commit"] = None
        write_zotero_bridge_bundle_state(self.profile, state)
        logger.warning(
            "Zotero Bridge bundle update failed; keeping previous bundle",
            extra={
                "component": "engine_management.zotero_bridge_bundle_auto_update",
                "action": action,
                "error_type": type(exc).__name__,
            },
            exc_info=True,
        )

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


def _optional_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


zotero_bridge_bundle_auto_update_manager = ZoteroBridgeBundleAutoUpdateManager()
