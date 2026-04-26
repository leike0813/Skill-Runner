import json
import logging
import os
import re
import shutil
import stat
import subprocess
import time
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional
import tomlkit
from tomlkit.exceptions import TOMLKitError

from server.config_registry import keys
from server.config import config
from server.engines.claude.adapter.sandbox_probe import (
    CLAUDE_SANDBOX_DEPENDENCY_MISSING,
    CLAUDE_SANDBOX_PROBE_KIND,
    CLAUDE_SANDBOX_RUNTIME_UNAVAILABLE,
    ClaudeSandboxProbeResult,
    load_claude_sandbox_probe,
    write_claude_sandbox_probe,
)
from server.engines.claude.adapter.state_paths import ensure_claude_active_state
from server.engines.codex.adapter.sandbox_probe import (
    CODEX_SANDBOX_DEPENDENCY_MISSING,
    CODEX_SANDBOX_DISABLED_BY_ENV,
    CODEX_SANDBOX_PROBE_KIND,
    CODEX_SANDBOX_RUNTIME_UNAVAILABLE,
    CodexSandboxProbeResult,
    load_codex_sandbox_probe,
    write_codex_sandbox_probe,
)
from server.models import (
    EngineInteractiveProfile,
    EngineResumeCapability,
)
from server.runtime.adapter.common.profile_loader import (
    AdapterProfile,
    load_adapter_profile,
)
from server.services.engine_management.runtime_profile import (
    RuntimeProfile,
    get_runtime_profile,
)

logger = logging.getLogger(__name__)

TTYD_BINARY_CANDIDATES = ["ttyd", "ttyd.exe", "ttyd.cmd"]
WINDOWS_NPM_BINARY_CANDIDATES = ("npm.cmd", "npm.exe", "npm.bat", "npm")

_DEFAULT_BOOTSTRAP_JSON_FALLBACKS: dict[str, Mapping[str, object]] = {
    "gemini": {
        "security": {
            "auth": {
                "selectedType": "oauth-personal",
            }
        }
    },
    "opencode": {
        "$schema": "https://opencode.ai/config.json",
        "plugin": ["opencode-antigravity-auth"],
    },
    "claude": {
        "hasCompletedOnboarding": True,
    },
    "qwen": {
        "general": {"enableAutoUpdate": False, "checkpointing": {"enabled": False}}
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
_CODEX_SANDBOX_INIT_FAILURE_MARKERS = (
    "uid_map",
    "operation not permitted",
    "permission denied",
    "setting up uid map",
)
_CLAUDE_SECCOMP_RELATIVE_PATHS = (
    Path("vendor/seccomp/x64/apply-seccomp"),
    Path("vendor/seccomp/arm64/apply-seccomp"),
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _supported_engines() -> tuple[str, ...]:
    return tuple(keys.ENGINE_KEYS)


def _load_bootstrap_json(
    filename: str, fallback: Mapping[str, object]
) -> Dict[str, Any]:
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

    def default_bootstrap_engines(self) -> tuple[str, ...]:
        configured = self._configured_default_bootstrap_engines()
        return tuple(
            engine for engine in configured if engine in self.supported_engines()
        )

    def resolve_bootstrap_targets(
        self, engine_spec: str | None = None
    ) -> dict[str, Any]:
        raw_spec = engine_spec
        if raw_spec is None:
            raw_spec = os.environ.get("SKILL_RUNNER_BOOTSTRAP_ENGINES", "")
        normalized_spec = str(raw_spec or "").strip().lower()
        supported = list(self.supported_engines())

        if not normalized_spec:
            requested = list(self.default_bootstrap_engines())
            resolved_mode = "subset"
            effective_spec = ",".join(requested)
        elif normalized_spec == "all":
            requested = supported
            resolved_mode = "all"
            effective_spec = "all"
        elif normalized_spec == "none":
            requested = []
            resolved_mode = "none"
            effective_spec = "none"
        else:
            requested = self._normalize_engine_spec_list(normalized_spec)
            resolved_mode = "subset"
            effective_spec = ",".join(requested)

        skipped = [engine for engine in supported if engine not in set(requested)]
        return {
            "raw_spec": str(raw_spec or ""),
            "effective_spec": effective_spec,
            "resolved_mode": resolved_mode,
            "requested_engines": requested,
            "skipped_engines": skipped,
        }

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
            elif engine == "claude":
                ensure_claude_active_state(
                    self.profile.agent_home,
                    bootstrap_payload=bootstrap_payload,
                )
            else:
                self._ensure_json_file(bootstrap_path, bootstrap_payload)
            self._apply_layout_normalizer(engine, bootstrap_path, bootstrap_payload)
            self._ensure_bootstrap_sidecars(engine)
        self._sync_claude_agent_home_mcp()

    def _sync_claude_agent_home_mcp(self) -> None:
        try:
            from jsonschema import ValidationError  # type: ignore[import-untyped]

            from server.engines.claude.adapter.mcp_materializer import sync_claude_agent_home_mcp
            from server.services.mcp import McpConfigError, load_mcp_registry, mcp_secret_store

            sync_claude_agent_home_mcp(
                agent_home=self.profile.agent_home,
                registry=load_mcp_registry(),
                secret_resolver=mcp_secret_store.get_secret,
            )
        except (McpConfigError, OSError, RuntimeError, TypeError, ValueError, ValidationError):
            logger.warning("Failed to synchronize Claude agent-home MCP state", exc_info=True)

    def collect_status(self) -> Dict[str, EngineStatus]:
        result: Dict[str, EngineStatus] = {}
        for engine in self.supported_engines():
            result[engine] = self.collect_engine_status(engine)
        return result

    def collect_sandbox_status(self, engine: str) -> Dict[str, Any]:
        normalized = engine.strip().lower()
        if normalized == "codex":
            codex_probe = self.get_codex_sandbox_probe()
            dependency_status = "n/a" if codex_probe.status == "disabled" else (
                "ready" if codex_probe.available else "warning"
            )
            return {
                "available": codex_probe.available,
                "status": codex_probe.status,
                "declared_enabled": codex_probe.declared_enabled,
                "dependency_status": dependency_status,
                "dependencies": dict(codex_probe.dependencies),
                "missing_dependencies": list(codex_probe.missing_dependencies),
                "warning_code": codex_probe.warning_code,
                "message": codex_probe.message,
                "checked_at": codex_probe.checked_at,
                "probe_kind": codex_probe.probe_kind,
            }

        if normalized != "claude":
            return {
                "available": False,
                "status": "n/a",
                "declared_enabled": False,
                "dependency_status": "n/a",
                "dependencies": {},
                "missing_dependencies": [],
                "warning_code": None,
                "message": "",
                "checked_at": None,
                "probe_kind": None,
            }

        declared_enabled = self._claude_sandbox_declared_enabled()
        claude_probe = load_claude_sandbox_probe(self.profile.agent_home)
        if claude_probe is None:
            message = "Claude sandbox bootstrap probe has not been recorded yet."
            return {
                "available": declared_enabled,
                "status": "unknown",
                "declared_enabled": declared_enabled,
                "dependency_status": "ready" if declared_enabled else "n/a",
                "dependencies": {},
                "missing_dependencies": [],
                "warning_code": None,
                "message": message,
                "checked_at": None,
                "probe_kind": None,
            }

        return {
            "available": claude_probe.available,
            "status": claude_probe.status,
            "declared_enabled": claude_probe.declared_enabled,
            "dependency_status": "ready" if claude_probe.available else "warning",
            "dependencies": dict(claude_probe.dependencies),
            "missing_dependencies": list(claude_probe.missing_dependencies),
            "warning_code": claude_probe.warning_code,
            "message": claude_probe.message,
            "checked_at": claude_probe.checked_at,
            "probe_kind": claude_probe.probe_kind,
        }

    def get_codex_sandbox_probe(
        self,
        *,
        force_refresh: bool = False,
    ) -> CodexSandboxProbeResult:
        if not force_refresh:
            cached = load_codex_sandbox_probe(self.profile.agent_home)
            if cached is not None:
                return cached
        probe = self._probe_codex_sandbox_status()
        write_codex_sandbox_probe(agent_home=self.profile.agent_home, probe=probe)
        return probe

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

        dynamic_args = list(
            self._engine_profile(engine).cli_management.resume_probe.dynamic_args
        )
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
        except (FileNotFoundError, OSError):
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

    def ensure_installed(
        self, engine_spec: str | None = None
    ) -> Dict[str, CommandResult]:
        results: Dict[str, CommandResult] = {}
        targets = self.resolve_bootstrap_targets(engine_spec)["requested_engines"]
        for engine in targets:
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
        npm_cmd = self._resolve_npm_command(env)
        started_at = time.perf_counter()
        claude_package = self._engine_profile("claude").cli_management.package
        logger.info(
            "event=agent_cli.command.start action=install_package package=%s command=%s mode=%s platform=%s",
            package,
            npm_cmd,
            self.profile.mode,
            self.profile.platform,
        )
        try:
            result = subprocess.run(
                [npm_cmd, "install", "-g", package],
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            logger.info(
                "event=agent_cli.command.result action=install_package package=%s outcome=%s returncode=%s duration_ms=%s",
                package,
                "ok" if result.returncode == 0 else "failed",
                result.returncode,
                duration_ms,
            )
            if result.returncode == 0 and package == claude_package:
                repaired, errors = self._repair_claude_seccomp_helpers()
                if repaired:
                    logger.info(
                        "event=agent_cli.command.result action=repair_claude_seccomp_helpers outcome=ok repaired=%s",
                        [str(path) for path in repaired],
                    )
                if errors:
                    logger.warning(
                        "event=agent_cli.command.result action=repair_claude_seccomp_helpers outcome=failed errors=%s",
                        errors,
                    )
            return CommandResult(
                returncode=result.returncode,
                stdout=result.stdout or "",
                stderr=result.stderr or "",
            )
        except OSError as exc:
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            logger.warning(
                "event=agent_cli.command.result action=install_package package=%s outcome=exception error_type=%s duration_ms=%s",
                package,
                type(exc).__name__,
                duration_ms,
                exc_info=True,
            )
            return CommandResult(
                returncode=127,
                stdout="",
                stderr=str(exc),
            )

    def _run_command(self, argv: list[str], timeout_sec: int = 5) -> CommandResult:
        env = self.profile.build_subprocess_env()
        started_at = time.perf_counter()
        logger.debug(
            "event=agent_cli.command.start action=run_command command=%s timeout_sec=%s",
            self._command_preview(argv),
            timeout_sec,
        )
        try:
            result = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                check=False,
                env=env,
                timeout=timeout_sec,
            )
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            logger.debug(
                "event=agent_cli.command.result action=run_command command=%s outcome=%s returncode=%s duration_ms=%s",
                self._command_preview(argv),
                "ok" if result.returncode == 0 else "failed",
                result.returncode,
                duration_ms,
            )
            return CommandResult(
                returncode=result.returncode,
                stdout=result.stdout or "",
                stderr=result.stderr or "",
            )
        except subprocess.TimeoutExpired as exc:
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            stdout = exc.stdout or ""
            stderr = exc.stderr or "timeout"
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")
            logger.warning(
                "event=agent_cli.command.result action=run_command command=%s outcome=timeout returncode=124 duration_ms=%s",
                self._command_preview(argv),
                duration_ms,
            )
            return CommandResult(
                returncode=124,
                stdout=stdout,
                stderr=stderr,
            )
        except OSError as exc:
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            logger.warning(
                "event=agent_cli.command.result action=run_command command=%s outcome=exception error_type=%s duration_ms=%s",
                self._command_preview(argv),
                type(exc).__name__,
                duration_ms,
                exc_info=True,
            )
            return CommandResult(
                returncode=127,
                stdout="",
                stderr=str(exc),
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
        candidates = self._ordered_binary_candidates(
            profile.cli_management.binary_candidates
        )
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
        candidates = self._ordered_binary_candidates(
            profile.cli_management.binary_candidates
        )
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
        managed_path = os.pathsep.join(
            str(path) for path in self.profile.managed_bin_dirs
        )
        ttyd_candidates = self._ordered_binary_candidates(TTYD_BINARY_CANDIDATES)
        for name in ttyd_candidates:
            resolved = shutil.which(name, path=managed_path)
            if resolved:
                return Path(resolved)
        for name in ttyd_candidates:
            resolved = shutil.which(name, path=os.environ.get("PATH", ""))
            if resolved:
                return Path(resolved)
        return None

    def _resolve_npm_command(self, env: Mapping[str, str]) -> str:
        explicit = str(
            env.get("SKILL_RUNNER_NPM_COMMAND")
            or os.environ.get("SKILL_RUNNER_NPM_COMMAND", "")
        ).strip()
        if explicit:
            explicit_path = Path(explicit)
            if explicit_path.exists():
                return str(explicit_path)
            logger.warning(
                "Configured SKILL_RUNNER_NPM_COMMAND does not exist: %s",
                explicit,
            )
        path = env.get("PATH", "")
        if self.profile.platform == "windows":
            for candidate in WINDOWS_NPM_BINARY_CANDIDATES:
                resolved = shutil.which(candidate, path=path)
                if resolved:
                    return resolved
            for candidate in WINDOWS_NPM_BINARY_CANDIDATES:
                resolved = shutil.which(candidate, path=os.environ.get("PATH", ""))
                if resolved:
                    return resolved
            return WINDOWS_NPM_BINARY_CANDIDATES[0]
        resolved = shutil.which("npm", path=path)
        return resolved or "npm"

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
            result[rule.source] = (
                self.profile.agent_home / rule.target_relpath
            ).exists()
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
            matched = all(
                credential_files.get(source, False) for source in policy.sources
            )
        else:
            matched = any(
                credential_files.get(source, False) for source in policy.sources
            )
        if not matched:
            return False

        return True

    def _engine_bootstrap_payload(self, engine: str) -> Mapping[str, object] | str:
        profile = self._engine_profile(engine)
        bootstrap_path = str(profile.resolve_bootstrap_path())
        bootstrap_format = profile.cli_management.layout.bootstrap_format
        if bootstrap_format == "json":
            fallback = _DEFAULT_BOOTSTRAP_JSON_FALLBACKS.get(engine)
            if fallback is None:
                raise RuntimeError(
                    f"Missing JSON bootstrap fallback for engine: {engine}"
                )
            return _load_bootstrap_json(bootstrap_path, fallback)
        fallback_text = _DEFAULT_BOOTSTRAP_TEXT_FALLBACKS.get(engine)
        if fallback_text is None:
            raise RuntimeError(f"Missing text bootstrap fallback for engine: {engine}")
        return _load_bootstrap_text(bootstrap_path, fallback_text)

    def _engine_bootstrap_target_path(self, engine: str) -> Path:
        profile = self._engine_profile(engine)
        return (
            self.profile.agent_home
            / profile.cli_management.layout.bootstrap_target_relpath
        )

    def _command_exists_any(self, names: Iterable[str]) -> bool:
        return self._resolve_command_any(names) is not None

    def _resolve_command_any(self, names: Iterable[str]) -> str | None:
        build_env = getattr(self.profile, "build_subprocess_env", None)
        env = build_env() if callable(build_env) else dict(os.environ)
        path_env = env.get("PATH", os.environ.get("PATH", ""))
        for name in names:
            resolved = shutil.which(name, path=path_env)
            if resolved:
                return resolved
            resolved = shutil.which(name, path=os.environ.get("PATH", ""))
            if resolved:
                return resolved
        return None

    def _claude_sandbox_declared_enabled(self) -> bool:
        profile = self._load_engine_profile_or_none("claude")
        if profile is None:
            return False
        enforced_path = profile.resolve_enforced_config_path()
        try:
            payload = json.loads(enforced_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            return False
        if not isinstance(payload, dict):
            return False
        sandbox = payload.get("sandbox")
        if not isinstance(sandbox, dict):
            return False
        return bool(sandbox.get("enabled"))

    def _claude_managed_package_root(self) -> Path:
        return (
            self.profile.npm_prefix
            / "lib"
            / "node_modules"
            / "@anthropic-ai"
            / "claude-code"
        )

    def _claude_seccomp_helper_paths(self) -> tuple[Path, ...]:
        package_root = self._claude_managed_package_root()
        return tuple(package_root / relpath for relpath in _CLAUDE_SECCOMP_RELATIVE_PATHS)

    def _repair_claude_seccomp_helpers(self) -> tuple[list[Path], list[str]]:
        repaired: list[Path] = []
        errors: list[str] = []
        for path in self._claude_seccomp_helper_paths():
            if not path.exists():
                continue
            if os.access(path, os.X_OK):
                continue
            try:
                current_mode = stat.S_IMODE(path.stat().st_mode)
                os.chmod(
                    path,
                    current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH,
                )
            except OSError as exc:
                errors.append(f"{path}: {exc}")
                continue
            if os.access(path, os.X_OK):
                repaired.append(path)
            else:
                errors.append(f"{path}: still not executable after chmod")
        return repaired, errors

    def _codex_sandbox_declared_enabled(self) -> bool:
        if os.environ.get("LANDLOCK_ENABLED") == "0":
            return False
        profile = self._load_engine_profile_or_none("codex")
        if profile is None:
            return False
        enforced_path = profile.resolve_enforced_config_path()
        try:
            payload = tomlkit.parse(enforced_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, TOMLKitError, ValueError):
            return True
        if not isinstance(payload, dict):
            return True
        profiles_obj = payload.get("profiles", {})
        if not isinstance(profiles_obj, dict):
            return True
        profile_cfg = profiles_obj.get("skill-runner", {})
        if not isinstance(profile_cfg, dict):
            return True
        sandbox_mode = str(profile_cfg.get("sandbox_mode") or "").strip().lower()
        if not sandbox_mode:
            return True
        return sandbox_mode != "danger-full-access"

    def _probe_claude_sandbox_status(self) -> ClaudeSandboxProbeResult:
        declared_enabled = self._claude_sandbox_declared_enabled()
        if not declared_enabled:
            return ClaudeSandboxProbeResult(
                declared_enabled=False,
                available=False,
                status="disabled",
                warning_code=None,
                message="Claude sandbox is disabled by enforced configuration.",
                dependencies={},
                missing_dependencies=[],
                checked_at=_utc_now_iso(),
                probe_kind=CLAUDE_SANDBOX_PROBE_KIND,
            )

        seccomp_helper_paths = self._claude_seccomp_helper_paths()
        existing_seccomp_helpers = [path for path in seccomp_helper_paths if path.exists()]
        claude_cli_installed = (
            self.resolve_managed_engine_command("claude") is not None
            or bool(existing_seccomp_helpers)
        )
        repaired_helpers: list[Path] = []
        repair_errors: list[str] = []
        if claude_cli_installed:
            repaired_helpers, repair_errors = self._repair_claude_seccomp_helpers()
            existing_seccomp_helpers = [path for path in seccomp_helper_paths if path.exists()]
        seccomp_helpers_ready = (not claude_cli_installed) or (
            bool(existing_seccomp_helpers)
            and all(os.access(path, os.X_OK) for path in existing_seccomp_helpers)
        )
        dependency_checks = {
            "bubblewrap": self._resolve_command_any(("bwrap", "bubblewrap"))
            is not None,
            "socat": self._resolve_command_any(("socat",)) is not None,
            "claude_seccomp_helper": seccomp_helpers_ready,
        }
        missing_dependencies = [
            name
            for name, present in dependency_checks.items()
            if not present and name != "claude_seccomp_helper"
        ]
        checked_at = _utc_now_iso()
        if missing_dependencies:
            return ClaudeSandboxProbeResult(
                declared_enabled=True,
                available=False,
                status="unavailable",
                warning_code=CLAUDE_SANDBOX_DEPENDENCY_MISSING,
                message=(
                    "Claude sandbox dependencies missing: "
                    + ", ".join(missing_dependencies)
                    + ". Headless runs will disable Claude sandbox."
                ),
                dependencies=dependency_checks,
                missing_dependencies=missing_dependencies,
                checked_at=checked_at,
                probe_kind=CLAUDE_SANDBOX_PROBE_KIND,
            )

        if not seccomp_helpers_ready:
            if not existing_seccomp_helpers:
                helper_detail = "missing vendor/seccomp/apply-seccomp helper"
            elif repair_errors:
                helper_detail = repair_errors[0]
            else:
                helper_detail = f"{existing_seccomp_helpers[0]} is not executable"
            if repaired_helpers:
                helper_detail = (
                    f"{helper_detail}; attempted self-heal for "
                    + ", ".join(str(path) for path in repaired_helpers)
                )
            return ClaudeSandboxProbeResult(
                declared_enabled=True,
                available=False,
                status="unavailable",
                warning_code=CLAUDE_SANDBOX_RUNTIME_UNAVAILABLE,
                message=(
                    "Claude sandbox runtime unavailable: "
                    f"{helper_detail}. Headless runs will disable Claude sandbox."
                ),
                dependencies=dependency_checks,
                missing_dependencies=[],
                checked_at=checked_at,
                probe_kind=CLAUDE_SANDBOX_PROBE_KIND,
            )

        bubblewrap_cmd = self._resolve_command_any(("bwrap", "bubblewrap"))
        if not bubblewrap_cmd:
            return ClaudeSandboxProbeResult(
                declared_enabled=True,
                available=False,
                status="unavailable",
                warning_code=CLAUDE_SANDBOX_DEPENDENCY_MISSING,
                message="Claude sandbox dependencies missing: bubblewrap. Headless runs will disable Claude sandbox.",
                dependencies=dependency_checks,
                missing_dependencies=["bubblewrap"],
                checked_at=checked_at,
                probe_kind=CLAUDE_SANDBOX_PROBE_KIND,
            )

        result = self._run_command(
            [
                bubblewrap_cmd,
                "--unshare-net",
                "--ro-bind",
                "/",
                "/",
                "--proc",
                "/proc",
                "--dev",
                "/dev",
                "/bin/sh",
                "-lc",
                "printf sandbox-ok",
            ],
            timeout_sec=3,
        )
        if result.returncode == 0:
            return ClaudeSandboxProbeResult(
                declared_enabled=True,
                available=True,
                status="available",
                warning_code=None,
                message="Claude sandbox runtime probe succeeded.",
                dependencies=dependency_checks,
                missing_dependencies=[],
                checked_at=checked_at,
                probe_kind=CLAUDE_SANDBOX_PROBE_KIND,
            )

        detail = (
            (result.stderr or "").strip() or (result.stdout or "").strip()
        ).splitlines()
        first_line = detail[0] if detail else f"exit={result.returncode}"
        return ClaudeSandboxProbeResult(
            declared_enabled=True,
            available=False,
            status="unavailable",
            warning_code=CLAUDE_SANDBOX_RUNTIME_UNAVAILABLE,
            message=(
                "Claude sandbox runtime unavailable: "
                f"{first_line}. Headless runs will disable Claude sandbox."
            ),
            dependencies=dependency_checks,
            missing_dependencies=[],
            checked_at=checked_at,
            probe_kind=CLAUDE_SANDBOX_PROBE_KIND,
        )

    def _probe_codex_sandbox_status(self) -> CodexSandboxProbeResult:
        declared_enabled = self._codex_sandbox_declared_enabled()
        checked_at = _utc_now_iso()
        if not declared_enabled:
            return CodexSandboxProbeResult(
                declared_enabled=False,
                available=False,
                status="disabled",
                warning_code=CODEX_SANDBOX_DISABLED_BY_ENV,
                message=(
                    "Codex sandbox is disabled by environment or enforced configuration. "
                    "Headless runs will use --yolo and sandbox_mode=danger-full-access."
                ),
                dependencies={},
                missing_dependencies=[],
                checked_at=checked_at,
                probe_kind=CODEX_SANDBOX_PROBE_KIND,
            )

        bubblewrap_cmd = self._resolve_command_any(("bwrap", "bubblewrap"))
        dependency_checks = {"bubblewrap": bubblewrap_cmd is not None}
        if bubblewrap_cmd is None:
            return CodexSandboxProbeResult(
                declared_enabled=True,
                available=False,
                status="unavailable",
                warning_code=CODEX_SANDBOX_DEPENDENCY_MISSING,
                message=(
                    "Codex sandbox dependency missing: bubblewrap. "
                    "Headless runs will use --yolo and sandbox_mode=danger-full-access."
                ),
                dependencies=dependency_checks,
                missing_dependencies=["bubblewrap"],
                checked_at=checked_at,
                probe_kind=CODEX_SANDBOX_PROBE_KIND,
            )

        result = self._run_command(
            [
                bubblewrap_cmd,
                "--ro-bind",
                "/",
                "/",
                "--proc",
                "/proc",
                "--dev",
                "/dev",
                "/bin/sh",
                "-lc",
                "printf sandbox-ok",
            ],
            timeout_sec=3,
        )
        if result.returncode == 0:
            return CodexSandboxProbeResult(
                declared_enabled=True,
                available=True,
                status="available",
                warning_code=None,
                message="Codex sandbox runtime probe succeeded.",
                dependencies=dependency_checks,
                missing_dependencies=[],
                checked_at=checked_at,
                probe_kind=CODEX_SANDBOX_PROBE_KIND,
            )

        detail = ((result.stderr or "").strip() or (result.stdout or "").strip()).splitlines()
        first_line = detail[0] if detail else f"exit={result.returncode}"
        normalized_first_line = first_line.lower()
        if any(marker in normalized_first_line for marker in _CODEX_SANDBOX_INIT_FAILURE_MARKERS):
            message = (
                "Codex sandbox runtime unavailable: "
                f"{first_line}. Headless runs will use --yolo and sandbox_mode=danger-full-access."
            )
        else:
            message = (
                "Codex sandbox smoke test failed: "
                f"{first_line}. Headless runs will use --yolo and sandbox_mode=danger-full-access."
            )
        return CodexSandboxProbeResult(
            declared_enabled=True,
            available=False,
            status="unavailable",
            warning_code=CODEX_SANDBOX_RUNTIME_UNAVAILABLE,
            message=message,
            dependencies=dependency_checks,
            missing_dependencies=[],
            checked_at=checked_at,
            probe_kind=CODEX_SANDBOX_PROBE_KIND,
        )

    def _configured_default_bootstrap_engines(self) -> tuple[str, ...]:
        raw = config.SYSTEM.DEFAULT_BOOTSTRAP_ENGINES
        if isinstance(raw, str):
            return tuple(self._normalize_engine_spec_list(raw))
        if isinstance(raw, Iterable):
            requested: list[str] = []
            seen: set[str] = set()
            for item in raw:
                normalized = str(item).strip().lower()
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                requested.append(normalized)
            return tuple(requested)
        return ()

    def _ensure_bootstrap_sidecars(self, engine: str) -> None:
        if engine == "codex":
            self.get_codex_sandbox_probe(force_refresh=True)
            return
        if engine != "claude":
            return
        self._ensure_json_file(
            self.profile.agent_home / ".claude" / "settings.json", {}
        )
        probe = self._probe_claude_sandbox_status()
        write_claude_sandbox_probe(agent_home=self.profile.agent_home, probe=probe)

    def _apply_layout_normalizer(
        self,
        engine: str,
        bootstrap_path: Path,
        bootstrap_payload: Mapping[str, object] | str,
    ) -> None:
        strategy = self._engine_profile(engine).cli_management.layout.normalize_strategy
        if strategy is None:
            return
        raise RuntimeError(f"Unknown normalize strategy: {strategy}")

    def _ensure_json_file(self, path: Path, payload: Mapping[str, object]) -> None:
        if path.exists():
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(dict(payload), indent=2) + "\n", encoding="utf-8")

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

    def _ordered_binary_candidates(self, candidates: Iterable[str]) -> list[str]:
        names = [str(item) for item in candidates]
        if self.profile.platform != "windows":
            return names
        return sorted(names, key=self._windows_candidate_priority)

    @staticmethod
    def _windows_candidate_priority(name: str) -> tuple[int, str]:
        suffix = Path(name).suffix.lower()
        rank = {
            ".cmd": 0,
            ".exe": 1,
            ".bat": 2,
            ".com": 3,
        }.get(suffix, 10)
        return rank, name.lower()

    @staticmethod
    def _command_preview(
        argv: Iterable[str], *, max_parts: int = 5, max_len: int = 160
    ) -> str:
        parts = [str(part) for part in argv]
        preview_parts = parts[:max_parts]
        preview = " ".join(preview_parts)
        if len(parts) > max_parts:
            preview = f"{preview} ..."
        if len(preview) > max_len:
            preview = preview[: max_len - 14].rstrip() + "...(truncated)"
        return preview

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

    def _normalize_engine_spec_list(self, raw: str) -> list[str]:
        requested: list[str] = []
        seen: set[str] = set()
        supported = set(self.supported_engines())
        for item in raw.split(","):
            engine = item.strip().lower()
            if not engine:
                continue
            if engine in {"all", "none"}:
                raise ValueError(
                    "engine spec must not mix 'all' or 'none' with engine names"
                )
            if engine not in supported:
                raise ValueError(
                    "Unsupported engine in bootstrap set: "
                    f"{engine}. Supported: {', '.join(self.supported_engines())}"
                )
            if engine not in seen:
                seen.add(engine)
                requested.append(engine)
        if not requested:
            raise ValueError(
                "bootstrap engine set must not be empty unless using 'none'"
            )
        return requested


def format_status_payload(
    status: Dict[str, EngineStatus],
) -> Dict[str, Dict[str, object]]:
    return {
        engine: {"present": item.present, "version": item.version}
        for engine, item in status.items()
    }


def format_auth_status_payload(
    status: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    return {engine: dict(payload) for engine, payload in status.items()}


def summarize_install_failures(results: Dict[str, CommandResult]) -> Iterable[str]:
    for engine, result in results.items():
        if result.returncode != 0:
            yield f"{engine}: exit={result.returncode}"
