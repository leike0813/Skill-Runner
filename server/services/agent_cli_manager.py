import json
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

from .runtime_profile import RuntimeProfile, get_runtime_profile

logger = logging.getLogger(__name__)


ENGINE_PACKAGES = {
    "codex": "@openai/codex",
    "gemini": "@google/gemini-cli",
    "iflow": "@iflow-ai/iflow-cli",
}

ENGINE_BINARY_CANDIDATES = {
    "codex": ["codex", "codex.cmd", "codex.exe"],
    "gemini": ["gemini", "gemini.cmd", "gemini.exe"],
    "iflow": ["iflow", "iflow.cmd", "iflow.exe"],
}
TTYD_BINARY_CANDIDATES = ["ttyd", "ttyd.exe", "ttyd.cmd"]

CREDENTIAL_IMPORT_RULES = {
    "codex": ["auth.json"],
    "gemini": ["google_accounts.json", "oauth_creds.json"],
    "iflow": ["iflow_accounts.json", "oauth_creds.json"],
}

DEFAULT_GEMINI_SETTINGS = {
    "security": {
        "auth": {
            "selectedType": "oauth-personal",
        }
    }
}

DEFAULT_IFLOW_SETTINGS = {
    "selectedAuthType": "oauth-iflow",
    "baseUrl": "https://apis.iflow.cn/v1",
}

DEFAULT_CODEX_CONFIG = 'cli_auth_credentials_store = "file"\n'
UI_XTERM_PACKAGE = "@xterm/xterm@5.5.0"
UI_XTERM_FIT_PACKAGE = "@xterm/addon-fit@0.10.0"


@dataclass(frozen=True)
class EngineStatus:
    present: bool
    version: str


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


class AgentCliManager:
    def __init__(self, profile: RuntimeProfile | None = None) -> None:
        self.profile = profile or get_runtime_profile()

    def ensure_layout(self) -> None:
        profile = self.profile
        profile.ensure_directories(
            [
                profile.agent_home / ".codex",
                profile.agent_home / ".gemini",
                profile.agent_home / ".iflow",
            ]
        )
        self._ensure_json_file(
            profile.agent_home / ".gemini" / "settings.json",
            DEFAULT_GEMINI_SETTINGS,
        )
        self._ensure_json_file(
            profile.agent_home / ".iflow" / "settings.json",
            DEFAULT_IFLOW_SETTINGS,
        )
        self._normalize_iflow_settings(
            profile.agent_home / ".iflow" / "settings.json",
        )
        codex_config = profile.agent_home / ".codex" / "config.toml"
        if not codex_config.exists():
            codex_config.write_text(DEFAULT_CODEX_CONFIG, encoding="utf-8")

    def ensure_ui_terminal_assets(self) -> Path:
        """
        Ensure xterm static assets are available under data/ui_static/xterm.
        Returns the mounted static root directory.
        """
        static_root = self.profile.data_dir / "ui_static"
        target_dir = static_root / "xterm"
        target_dir.mkdir(parents=True, exist_ok=True)
        target_js = target_dir / "xterm.js"
        target_css = target_dir / "xterm.css"
        target_fit = target_dir / "addon-fit.js"
        if target_js.exists() and target_css.exists():
            return static_root

        source_js, source_css = self._resolve_xterm_asset_sources()
        if source_js is None or source_css is None:
            install_result = self.install_package(UI_XTERM_PACKAGE)
            if install_result.returncode != 0:
                logger.warning(
                    "Failed to install xterm package for UI terminal: exit=%s stderr=%s",
                    install_result.returncode,
                    install_result.stderr.strip(),
                )
                return static_root
            source_js, source_css = self._resolve_xterm_asset_sources()

        if source_js and source_css:
            shutil.copy2(source_js, target_js)
            shutil.copy2(source_css, target_css)
        else:
            logger.warning("xterm static assets are missing after install attempt")

        # Optional addon: keep UI usable even when fit addon is unavailable.
        source_fit = self._resolve_xterm_fit_asset_source()
        if source_fit is None:
            fit_install = self.install_package(UI_XTERM_FIT_PACKAGE)
            if fit_install.returncode == 0:
                source_fit = self._resolve_xterm_fit_asset_source()
            else:
                logger.warning(
                    "Failed to install xterm fit addon: exit=%s stderr=%s",
                    fit_install.returncode,
                    fit_install.stderr.strip(),
                )
        if source_fit is not None:
            shutil.copy2(source_fit, target_fit)
        else:
            logger.info("xterm fit addon not available; UI terminal will run without auto-fit addon")
        return static_root

    def collect_status(self) -> Dict[str, EngineStatus]:
        result: Dict[str, EngineStatus] = {}
        for engine in ENGINE_PACKAGES:
            result[engine] = self.check_engine(engine)
        return result

    def check_engine(self, engine: str) -> EngineStatus:
        cmd = self.resolve_engine_command(engine)
        if cmd is None:
            return EngineStatus(present=False, version="")
        version = self.read_version(engine) or ""
        return EngineStatus(present=True, version=version)

    def read_version(self, engine: str) -> Optional[str]:
        cmd = self.resolve_engine_command(engine)
        if cmd is None:
            return None
        env = self.profile.build_subprocess_env()
        try:
            result = subprocess.run(
                [str(cmd), "--version"],
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )
        except FileNotFoundError:
            return None
        output = (result.stdout or "").strip() or (result.stderr or "").strip()
        if not output:
            return None
        return output.splitlines()[0].strip()

    def ensure_installed(self) -> Dict[str, CommandResult]:
        results: Dict[str, CommandResult] = {}
        for engine, package in ENGINE_PACKAGES.items():
            if self.resolve_managed_engine_command(engine) is None:
                results[engine] = self.install_package(package)
        return results

    def upgrade_all(self) -> Dict[str, CommandResult]:
        results: Dict[str, CommandResult] = {}
        for engine, package in ENGINE_PACKAGES.items():
            results[engine] = self.install_package(package)
        return results

    def upgrade_engine(self, engine: str) -> CommandResult:
        package = ENGINE_PACKAGES.get(engine)
        if not package:
            raise ValueError(f"Unsupported engine: {engine}")
        return self.install_package(package)

    def install_package(self, package: str) -> CommandResult:
        env = self.profile.build_subprocess_env()
        result = subprocess.run(
            ["npm", "install", "-g", package],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        return CommandResult(
            returncode=result.returncode,
            stdout=result.stdout or "",
            stderr=result.stderr or "",
        )

    def import_credentials(self, source_root: Path) -> Dict[str, list[str]]:
        source_root = source_root.resolve()
        copied: Dict[str, list[str]] = {}
        for engine, filenames in CREDENTIAL_IMPORT_RULES.items():
            src_engine = source_root / engine
            dst_engine = self.profile.agent_home / f".{engine}"
            dst_engine.mkdir(parents=True, exist_ok=True)
            copied_files: list[str] = []
            for filename in filenames:
                src = src_engine / filename
                if not src.exists():
                    continue
                dst = dst_engine / filename
                shutil.copy2(src, dst)
                copied_files.append(filename)
            copied[engine] = copied_files
        return copied

    def resolve_engine_command(self, engine: str) -> Optional[Path]:
        managed = self.resolve_managed_engine_command(engine)
        if managed is not None:
            return managed
        return self.resolve_global_engine_command(engine)

    def resolve_managed_engine_command(self, engine: str) -> Optional[Path]:
        candidates = ENGINE_BINARY_CANDIDATES.get(engine)
        if not candidates:
            return None
        for base in self.profile.managed_bin_dirs:
            for name in candidates:
                path = base / name
                if path.exists() and os.access(path, os.X_OK):
                    return path
        return None

    def resolve_global_engine_command(self, engine: str) -> Optional[Path]:
        candidates = ENGINE_BINARY_CANDIDATES.get(engine)
        if not candidates:
            return None
        global_path = self._build_global_only_path(os.environ.get("PATH", ""))
        for name in candidates:
            resolved = shutil.which(name, path=global_path)
            if resolved:
                return Path(resolved)
        return None

    def resolve_ttyd_command(self) -> Optional[Path]:
        explicit = os.environ.get("SKILL_RUNNER_TTYD_PATH", "").strip()
        if explicit:
            candidate = Path(explicit)
            if candidate.exists() and os.access(candidate, os.X_OK):
                return candidate
            return None
        managed_path = os.pathsep.join(str(path) for path in self.profile.managed_bin_dirs)
        for name in TTYD_BINARY_CANDIDATES:
            resolved = shutil.which(name, path=managed_path)
            if resolved:
                return Path(resolved)
        for name in TTYD_BINARY_CANDIDATES:
            resolved = shutil.which(name, path=os.environ.get("PATH", ""))
            if resolved:
                return Path(resolved)
        return None

    def collect_auth_status(self) -> Dict[str, Dict[str, Any]]:
        status: Dict[str, Dict[str, Any]] = {}
        for engine in ENGINE_PACKAGES:
            managed_cmd = self.resolve_managed_engine_command(engine)
            global_cmd = self.resolve_global_engine_command(engine)
            effective_cmd = managed_cmd or global_cmd
            effective_source = "missing"
            if managed_cmd is not None:
                effective_source = "managed"
            elif global_cmd is not None:
                effective_source = "global"

            credential_files = {
                filename: (self.profile.agent_home / f".{engine}" / filename).exists()
                for filename in CREDENTIAL_IMPORT_RULES.get(engine, [])
            }
            auth_ready = bool(effective_cmd) and all(credential_files.values())
            if engine == "iflow":
                auth_ready = auth_ready and self._is_iflow_settings_valid(
                    self.profile.agent_home / ".iflow" / "settings.json"
                )

            status[engine] = {
                "managed_present": managed_cmd is not None,
                "managed_cli_path": str(managed_cmd) if managed_cmd else None,
                "global_available": global_cmd is not None,
                "global_cli_path": str(global_cmd) if global_cmd else None,
                "effective_cli_path": str(effective_cmd) if effective_cmd else None,
                "effective_path_source": effective_source,
                "credential_files": credential_files,
                "auth_ready": auth_ready,
            }
        return status

    def _ensure_json_file(self, path: Path, payload: Mapping[str, object]) -> None:
        if path.exists():
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(dict(payload), indent=2) + "\n", encoding="utf-8")

    def _normalize_iflow_settings(self, path: Path) -> None:
        try:
            current = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(current, dict):
                current = {}
        except Exception:
            current = {}

        changed = False

        selected_auth = current.get("selectedAuthType")
        if not selected_auth or selected_auth == "iflow":
            current["selectedAuthType"] = DEFAULT_IFLOW_SETTINGS["selectedAuthType"]
            changed = True

        base_url = current.get("baseUrl")
        if not isinstance(base_url, str) or not base_url.startswith(("http://", "https://")):
            current["baseUrl"] = DEFAULT_IFLOW_SETTINGS["baseUrl"]
            changed = True

        if changed:
            path.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")

    def _is_iflow_settings_valid(self, path: Path) -> bool:
        try:
            current = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(current, dict):
                return False
            selected_auth = current.get("selectedAuthType")
            base_url = current.get("baseUrl")
            return (
                isinstance(selected_auth, str)
                and selected_auth == "oauth-iflow"
                and isinstance(base_url, str)
                and base_url.startswith(("http://", "https://"))
            )
        except Exception:
            return False

    def _build_global_only_path(self, base_path: str) -> str:
        if not base_path:
            return ""
        managed_roots = {str(path.resolve()) for path in self.profile.managed_bin_dirs}
        kept: list[str] = []
        for chunk in base_path.split(os.pathsep):
            if not chunk:
                continue
            try:
                resolved = str(Path(chunk).resolve())
            except Exception:
                resolved = chunk
            if resolved in managed_roots:
                continue
            kept.append(chunk)
        return os.pathsep.join(kept)

    def _resolve_xterm_asset_sources(self) -> tuple[Path | None, Path | None]:
        candidates = [
            self.profile.npm_prefix / "lib" / "node_modules" / "@xterm" / "xterm",
            self.profile.npm_prefix / "node_modules" / "@xterm" / "xterm",
        ]
        for base in candidates:
            source_js = base / "lib" / "xterm.js"
            source_css = base / "css" / "xterm.css"
            if source_js.exists() and source_css.exists():
                return source_js, source_css
        return None, None

    def _resolve_xterm_fit_asset_source(self) -> Path | None:
        candidates = [
            self.profile.npm_prefix / "lib" / "node_modules" / "@xterm" / "addon-fit",
            self.profile.npm_prefix / "node_modules" / "@xterm" / "addon-fit",
        ]
        for base in candidates:
            for rel in ("lib/addon-fit.js", "dist/addon-fit.js"):
                path = base / rel
                if path.exists():
                    return path
        return None


def format_status_payload(status: Dict[str, EngineStatus]) -> Dict[str, Dict[str, object]]:
    return {
        engine: {"present": item.present, "version": item.version}
        for engine, item in status.items()
    }


def format_auth_status_payload(status: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {engine: dict(payload) for engine, payload in status.items()}


def summarize_install_failures(results: Dict[str, CommandResult]) -> Iterable[str]:
    for engine, result in results.items():
        if result.returncode != 0:
            yield f"{engine}: exit={result.returncode}"
