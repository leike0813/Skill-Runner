import io
import json
import logging
import shutil
import threading
import zipfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from ..config import config
from .skill_install_store import skill_install_store
from .skill_registry import skill_registry
from .skill_package_validator import SkillPackageValidator


logger = logging.getLogger(__name__)


class SkillPackageManager:
    """Manages async skill package validation, installation, and update archive flow."""

    def __init__(self) -> None:
        self._apply_lock = threading.Lock()
        self.validator = SkillPackageValidator()

    def create_install_request(self, request_id: str, package_bytes: bytes) -> Path:
        requests_root = Path(config.SYSTEM.SKILL_INSTALLS_DIR) / "requests" / request_id
        requests_root.mkdir(parents=True, exist_ok=True)
        package_path = requests_root / "skill_package.zip"
        package_path.write_bytes(package_bytes)
        skill_install_store.create_install(request_id)
        return package_path

    def run_install(self, request_id: str) -> None:
        skill_install_store.update_running(request_id)
        try:
            skill_id, version, action = self._process_install(request_id)
            skill_install_store.update_succeeded(
                request_id=request_id,
                skill_id=skill_id,
                version=version,
                action=action
            )
        except Exception as exc:
            logger.exception("Skill package install failed for request %s", request_id)
            skill_install_store.update_failed(request_id, str(exc))
        finally:
            self._cleanup_request_files(request_id)

    def _process_install(self, request_id: str) -> Tuple[str, str, str]:
        package_path = Path(config.SYSTEM.SKILL_INSTALLS_DIR) / "requests" / request_id / "skill_package.zip"
        if not package_path.exists():
            raise ValueError("Install package not found")

        top_level = self._inspect_zip_top_level(package_path)
        staging_root = Path(config.SYSTEM.SKILLS_STAGING_DIR) / request_id
        if staging_root.exists():
            shutil.rmtree(staging_root, ignore_errors=True)
        staging_root.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(package_path, "r") as zf:
            zf.extractall(staging_root)

        staged_skill_dir = staging_root / top_level
        if not staged_skill_dir.exists() or not staged_skill_dir.is_dir():
            raise ValueError("Skill package extraction failed")

        skill_id, version = self._validate_staged_skill(staged_skill_dir, top_level)
        skills_dir = Path(config.SYSTEM.SKILLS_DIR)
        skills_dir.mkdir(parents=True, exist_ok=True)
        live_skill_dir = skills_dir / skill_id

        with self._apply_lock:
            if live_skill_dir.exists():
                old_version = self._read_installed_version(live_skill_dir)
                self._ensure_version_upgrade(old_version, version)
                self._archive_and_swap(
                    live_skill_dir=live_skill_dir,
                    staged_skill_dir=staged_skill_dir,
                    old_version=old_version
                )
                action = "update"
            else:
                shutil.move(str(staged_skill_dir), str(live_skill_dir))
                action = "install"

        skill_registry.scan_skills()
        return skill_id, version, action

    def _inspect_zip_top_level(self, package_path: Path) -> str:
        return self.validator.inspect_zip_top_level_from_path(package_path)

    def _validate_staged_skill(self, skill_dir: Path, top_level_dir: str) -> Tuple[str, str]:
        skill_id, version = self.validator.validate_skill_dir(
            skill_dir, top_level_dir, require_version=True
        )
        if not version:
            raise ValueError("runner.json must define a non-empty version")
        return skill_id, version

    def _read_installed_version(self, live_skill_dir: Path) -> str:
        runner_path = live_skill_dir / "assets" / "runner.json"
        if not runner_path.exists():
            raise ValueError("Existing skill missing assets/runner.json")
        try:
            runner = json.loads(runner_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("Existing skill has invalid runner.json") from exc
        version = runner.get("version")
        if not isinstance(version, str) or not version.strip():
            raise ValueError("Existing skill missing version in runner.json")
        version = version.strip()
        self.validator.parse_version(version)
        return version

    def _ensure_version_upgrade(self, old_version: str, new_version: str) -> None:
        self.validator.ensure_version_upgrade(old_version, new_version)

    def _archive_and_swap(self, live_skill_dir: Path, staged_skill_dir: Path, old_version: str) -> None:
        archive_dir = Path(config.SYSTEM.SKILLS_ARCHIVE_DIR) / live_skill_dir.name / old_version
        if archive_dir.exists():
            raise ValueError(
                f"Archive already exists for {live_skill_dir.name} version {old_version}"
            )
        archive_dir.parent.mkdir(parents=True, exist_ok=True)

        shutil.move(str(live_skill_dir), str(archive_dir))
        try:
            shutil.move(str(staged_skill_dir), str(live_skill_dir))
        except Exception as exc:
            # Attempt rollback to keep active skill unchanged.
            if not live_skill_dir.exists() and archive_dir.exists():
                shutil.move(str(archive_dir), str(live_skill_dir))
            raise ValueError(f"Failed to apply skill update: {exc}") from exc

    def _cleanup_request_files(self, request_id: str) -> None:
        requests_root = Path(config.SYSTEM.SKILL_INSTALLS_DIR) / "requests" / request_id
        staging_root = Path(config.SYSTEM.SKILLS_STAGING_DIR) / request_id
        if requests_root.exists():
            shutil.rmtree(requests_root, ignore_errors=True)
        if staging_root.exists():
            shutil.rmtree(staging_root, ignore_errors=True)


skill_package_manager = SkillPackageManager()
