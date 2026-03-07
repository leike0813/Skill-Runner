import json
import logging
import os
import re
import shutil
import subprocess
from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

from server.config_registry import keys
from server.models import (
    EngineInteractiveProfile,
    EngineResumeCapability,
)
from server.runtime.adapter.common.profile_loader import AdapterProfile, load_adapter_profile
from server.services.engine_management.runtime_profile import RuntimeProfile, get_runtime_profile

logger = logging.getLogger(__name__)

TTYD_BINARY_CANDIDATES = ["ttyd", "ttyd.exe", "ttyd.cmd"]

_DEFAULT_BOOTSTRAP_JSON_FALLBACKS: dict[str, Mapping[str, object]] = {
    "gemini": {
        "security": {
            "auth": {
                "selectedType": "oauth-personal",
            }
        }
    },
    "iflow": {
        "selectedAuthType": "oauth-iflow",
        "baseUrl": "https://apis.iflow.cn/v1",
    },
    "opencode": {
        "$schema": "https://opencode.ai/config.json",
        "plugin": ["opencode-antigravity-auth"],
    },
}
_DEFAULT_BOOTSTRAP_TEXT_FALLBACKS: dict[str, str] = {
    "codex": 'cli_auth_credentials_store = "file"\n',
}

_BOOTSTRAP_JSON_EXCEPTIONS = (
    OSError,
    UnicodeDecodeError,
    json.JSONDecodeError,
)
_BOOTSTRAP_TEXT_EXCEPTIONS = (
    OSError,
    UnicodeDecodeError,
)
_IFLOW_SETTINGS_PARSE_EXCEPTIONS = (
    OSError,
    UnicodeDecodeError,
    json.JSONDecodeError,
)
_PATH_RESOLVE_EXCEPTIONS = (
    OSError,
    RuntimeError,
    ValueError,
)
_SEMVER_PATTERN = re.compile(r"\b\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?\b")


def _supported_engines() -> tuple[str, ...]:
    return tuple(keys.ENGINE_KEYS)


def _load_bootstrap_json(filename: str, fallback: Mapping[str, object]) -> Dict[str, Any]:
    path = Path(filename)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
        logger.warning("Bootstrap config is not a JSON object: %s", path)
    except _BOOTSTRAP_JSON_EXCEPTIONS as exc:
        logger.warning(
            "Failed to load bootstrap config JSON: %s",
            path,
            extra={
                "component": "orchestration.agent_cli_manager",
                "action": "load_bootstrap_json",
                "error_type": type(exc).__name__,
                "fallback": "default_bootstrap_json",
            },
            exc_info=True,
        )
    return deepcopy(dict(fallback))


def _load_bootstrap_text(filename: str, fallback: str) -> str:
    path = Path(filename)
    try:
        return path.read_text(encoding="utf-8")
    except _BOOTSTRAP_TEXT_EXCEPTIONS as exc:
        logger.warning(
            "Failed to load bootstrap config text: %s",
            path,
            extra={
                "component": "orchestration.agent_cli_manager",
                "action": "load_bootstrap_text",
                "error_type": type(exc).__name__,
                "fallback": "default_bootstrap_text",
            },
            exc_info=True,
        )
    return fallback


@lru_cache(maxsize=8)
def _load_engine_profile(engine: str) -> AdapterProfile:
    normalized = engine.strip().lower()
    if normalized not in keys.ENGINE_KEYS:
        raise ValueError(f"Unsupported engine: {engine}")
    profile_path = (
        Path(__file__).resolve().parents[2]
        / "engines"
        / normalized
        / "adapter"
        / "adapter_profile.json"
    )
    return load_adapter_profile(normalized, profile_path)


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

    def supported_engines(self) -> tuple[str, ...]:
        return _supported_engines()

    def ensure_layout(self) -> None:
        profile = self.profile
        directory_set: set[Path] = set()
        for engine in self.supported_engines():
            layout = self._engine_profile(engine).cli_management.layout
            for relpath in layout.extra_dirs:
                directory_set.add(profile.agent_home / relpath)
        if directory_set:
            profile.ensure_directories(sorted(directory_set))

        for engine in self.supported_engines():
            bootstrap_path = self._engine_bootstrap_target_path(engine)
            bootstrap_payload = self._engine_bootstrap_payload(engine)
            if isinstance(bootstrap_payload, str):
                if not bootstrap_path.exists():
                    bootstrap_path.parent.mkdir(parents=True, exist_ok=True)
                    bootstrap_path.write_text(bootstrap_payload, encoding="utf-8")
            else:
                self._ensure_json_file(bootstrap_path, bootstrap_payload)
            self._apply_layout_normalizer(engine, bootstrap_path, bootstrap_payload)

    def collect_status(self) -> Dict[str, EngineStatus]:
        result: Dict[str, EngineStatus] = {}
        for engine in self.supported_engines():
            result[engine] = self.collect_engine_status(engine)
        return result

    def collect_engine_status(self, engine: str) -> EngineStatus:
        return self.check_engine(engine)

    def probe_resume_capability(self, engine: str) -> EngineResumeCapability:
        static = self._detect_resume_static(engine)
        if not static.supported:
            return static

        command = self.resolve_engine_command(engine)
        if command is None:
            return EngineResumeCapability(
                supported=False,
                probe_method="command",
                detail="cli_missing",
            )

        dynamic_args = list(self._engine_profile(engine).cli_management.resume_probe.dynamic_args)
        if not dynamic_args:
            return static

        result = self._run_command([str(command), *dynamic_args], timeout_sec=5)
        if result.returncode == 0:
            return EngineResumeCapability(
                supported=True,
                probe_method="command",
                detail="resume_probe_ok",
            )
        return EngineResumeCapability(
            supported=False,
            probe_method="command",
            detail=f"resume_probe_failed:{result.returncode}",
        )

    def resolve_interactive_profile(
        self,
        engine: str,
        session_timeout_sec: int,
    ) -> EngineInteractiveProfile:
        capability = self.probe_resume_capability(engine)
        reason = capability.detail or "resume_probe_unknown"
        if not capability.supported:
            reason = f"forced_resumable:{reason}"
        return EngineInteractiveProfile(
            reason=reason,
            session_timeout_sec=session_timeout_sec,
        )

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
        first_line = output.splitlines()[0].strip()
        normalized = self._normalize_version_text(first_line)
        return normalized or None

    def _normalize_version_text(self, raw: str) -> str:
        text = raw.strip()
        if not text:
            return ""
        match = _SEMVER_PATTERN.search(text)
        if match is not None:
            return match.group(0)
        return text

    def ensure_installed(self) -> Dict[str, CommandResult]:
        results: Dict[str, CommandResult] = {}
        for engine in self.supported_engines():
            if self.resolve_managed_engine_command(engine) is None:
                results[engine] = self.install_package(self.engine_package(engine))
        return results

    def upgrade_all(self) -> Dict[str, CommandResult]:
        results: Dict[str, CommandResult] = {}
        for engine in self.supported_engines():
            results[engine] = self.install_package(self.engine_package(engine))
        return results

    def upgrade_engine(self, engine: str) -> CommandResult:
        normalized = engine.strip().lower()
        if normalized not in self.supported_engines():
            raise ValueError(f"Unsupported engine: {engine}")
        package = self.engine_package(normalized)
        return self.install_package(package)

    def engine_package(self, engine: str) -> str:
        normalized = engine.strip().lower()
        if normalized not in self.supported_engines():
            raise ValueError(f"Unsupported engine: {engine}")
        return self._engine_profile(normalized).cli_management.package

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

    def _run_command(self, argv: list[str], timeout_sec: int = 5) -> CommandResult:
        env = self.profile.build_subprocess_env()
        try:
            result = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                check=False,
                env=env,
                timeout=timeout_sec,
            )
            return CommandResult(
                returncode=result.returncode,
                stdout=result.stdout or "",
                stderr=result.stderr or "",
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout or ""
            stderr = exc.stderr or "timeout"
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")
            return CommandResult(
                returncode=124,
                stdout=stdout,
                stderr=stderr,
            )

    def import_credentials(self, source_root: Path) -> Dict[str, list[str]]:
        source_root = source_root.resolve()
        copied: Dict[str, list[str]] = {}
        for engine in self.supported_engines():
            imports = self._engine_profile(engine).cli_management.credential_imports
            src_engine = source_root / engine
            copied_files: list[str] = []
            for rule in imports:
                src = src_engine / rule.source
                if not src.exists():
                    continue
                dst = self.profile.agent_home / rule.target_relpath
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                copied_files.append(rule.source)
            copied[engine] = copied_files
        return copied

    def resolve_engine_command(self, engine: str) -> Optional[Path]:
        managed = self.resolve_managed_engine_command(engine)
        if managed is not None:
            return managed
        return self.resolve_global_engine_command(engine)

    def resolve_managed_engine_command(self, engine: str) -> Optional[Path]:
        profile = self._load_engine_profile_or_none(engine)
        if profile is None:
            return None
        candidates = profile.cli_management.binary_candidates
        for base in self.profile.managed_bin_dirs:
            for name in candidates:
                path = base / name
                if path.exists() and os.access(path, os.X_OK):
                    return path
        return None

    def resolve_global_engine_command(self, engine: str) -> Optional[Path]:
        profile = self._load_engine_profile_or_none(engine)
        if profile is None:
            return None
        candidates = profile.cli_management.binary_candidates
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
        for engine in self.supported_engines():
            profile = self._engine_profile(engine)
            managed_cmd = self.resolve_managed_engine_command(engine)
            global_cmd = self.resolve_global_engine_command(engine)
            effective_cmd = managed_cmd or global_cmd
            effective_source = "missing"
            if managed_cmd is not None:
                effective_source = "managed"
            elif global_cmd is not None:
                effective_source = "global"

            credential_files = self._credential_status_paths(engine)
            credential_state = "unknown"
            credentials_present = self._evaluate_credentials_present(
                profile=profile,
                credential_files=credential_files,
                effective_cmd=effective_cmd,
            )
            if effective_cmd:
                credential_state = "present" if credentials_present else "missing"

            status[engine] = {
                "managed_present": managed_cmd is not None,
                "managed_cli_path": str(managed_cmd) if managed_cmd else None,
                "global_available": global_cmd is not None,
                "global_cli_path": str(global_cmd) if global_cmd else None,
                "effective_cli_path": str(effective_cmd) if effective_cmd else None,
                "effective_path_source": effective_source,
                "credential_files": credential_files,
                "credential_state": credential_state,
            }
        return status

    def _credential_status_paths(self, engine: str) -> Dict[str, bool]:
        profile = self._engine_profile(engine)
        result: Dict[str, bool] = {}
        for rule in profile.cli_management.credential_imports:
            result[rule.source] = (self.profile.agent_home / rule.target_relpath).exists()
        return result

    def _evaluate_credentials_present(
        self,
        *,
        profile: AdapterProfile,
        credential_files: Dict[str, bool],
        effective_cmd: Path | None,
    ) -> bool:
        if effective_cmd is None:
            return False

        policy = profile.cli_management.credential_policy
        if policy.mode == "all_of_sources":
            matched = all(credential_files.get(source, False) for source in policy.sources)
        else:
            matched = any(credential_files.get(source, False) for source in policy.sources)
        if not matched:
            return False

        validator = policy.settings_validator
        if validator == "iflow_oauth_settings":
            return self._is_iflow_settings_valid(self._engine_bootstrap_target_path(profile.engine))
        return True

    def _engine_bootstrap_payload(self, engine: str) -> Mapping[str, object] | str:
        profile = self._engine_profile(engine)
        bootstrap_path = str(profile.resolve_bootstrap_path())
        bootstrap_format = profile.cli_management.layout.bootstrap_format
        if bootstrap_format == "json":
            fallback = _DEFAULT_BOOTSTRAP_JSON_FALLBACKS.get(engine)
            if fallback is None:
                raise RuntimeError(f"Missing JSON bootstrap fallback for engine: {engine}")
            return _load_bootstrap_json(bootstrap_path, fallback)
        fallback_text = _DEFAULT_BOOTSTRAP_TEXT_FALLBACKS.get(engine)
        if fallback_text is None:
            raise RuntimeError(f"Missing text bootstrap fallback for engine: {engine}")
        return _load_bootstrap_text(bootstrap_path, fallback_text)

    def _engine_bootstrap_target_path(self, engine: str) -> Path:
        profile = self._engine_profile(engine)
        return self.profile.agent_home / profile.cli_management.layout.bootstrap_target_relpath

    def _apply_layout_normalizer(
        self,
        engine: str,
        bootstrap_path: Path,
        bootstrap_payload: Mapping[str, object] | str,
    ) -> None:
        strategy = self._engine_profile(engine).cli_management.layout.normalize_strategy
        if strategy is None:
            return
        if strategy == "iflow_settings_v1":
            if not isinstance(bootstrap_payload, Mapping):
                raise RuntimeError("iflow_settings_v1 normalizer expects JSON bootstrap payload")
            self._normalize_iflow_settings(bootstrap_path, bootstrap_payload)
            return
        raise RuntimeError(f"Unknown normalize strategy: {strategy}")

    def _ensure_json_file(self, path: Path, payload: Mapping[str, object]) -> None:
        if path.exists():
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(dict(payload), indent=2) + "\n", encoding="utf-8")

    def _normalize_iflow_settings(self, path: Path, defaults: Mapping[str, object]) -> None:
        selected_auth_default = str(defaults.get("selectedAuthType") or "oauth-iflow")
        base_url_default = str(defaults.get("baseUrl") or "https://apis.iflow.cn/v1")
        try:
            current = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(current, dict):
                current = {}
        except _IFLOW_SETTINGS_PARSE_EXCEPTIONS as exc:
            logger.warning(
                "Falling back to default iFlow settings: %s",
                path,
                extra={
                    "component": "orchestration.agent_cli_manager",
                    "action": "normalize_iflow_settings",
                    "error_type": type(exc).__name__,
                    "fallback": "default_iflow_settings",
                },
                exc_info=True,
            )
            current = {}

        changed = False

        selected_auth = current.get("selectedAuthType")
        if not selected_auth or selected_auth == "iflow":
            current["selectedAuthType"] = selected_auth_default
            changed = True

        base_url = current.get("baseUrl")
        if not isinstance(base_url, str) or not base_url.startswith(("http://", "https://")):
            current["baseUrl"] = base_url_default
            changed = True

        if changed:
            path.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")

    def _detect_resume_static(self, engine: str) -> EngineResumeCapability:
        command = self.resolve_engine_command(engine)
        if command is None:
            return EngineResumeCapability(
                supported=False,
                probe_method="command",
                detail="cli_missing",
            )

        hints = self._engine_profile(engine).cli_management.resume_probe.help_hints
        result = self._run_command([str(command), "--help"], timeout_sec=5)
        combined = f"{result.stdout}\n{result.stderr}".lower()
        if any(hint.lower() in combined for hint in hints):
            return EngineResumeCapability(
                supported=True,
                probe_method="command",
                detail="resume_flag_detected",
            )
        return EngineResumeCapability(
            supported=False,
            probe_method="command",
            detail="resume_flag_missing",
        )

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
        except _IFLOW_SETTINGS_PARSE_EXCEPTIONS as exc:
            logger.debug(
                "iFlow settings validation fallback",
                extra={
                    "component": "orchestration.agent_cli_manager",
                    "action": "validate_iflow_settings",
                    "error_type": type(exc).__name__,
                    "fallback": "auth_ready_false",
                },
                exc_info=True,
            )
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
            except _PATH_RESOLVE_EXCEPTIONS as exc:
                logger.debug(
                    "PATH entry resolve fallback",
                    extra={
                        "component": "orchestration.agent_cli_manager",
                        "action": "build_global_only_path",
                        "error_type": type(exc).__name__,
                        "fallback": "use_original_path_chunk",
                    },
                    exc_info=True,
                )
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

    def _engine_profile(self, engine: str) -> AdapterProfile:
        return _load_engine_profile(engine)

    def _load_engine_profile_or_none(self, engine: str) -> AdapterProfile | None:
        normalized = engine.strip().lower()
        if normalized not in self.supported_engines():
            return None
        return _load_engine_profile(normalized)


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
