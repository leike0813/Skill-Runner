import os
import platform
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable

from ..config import config


def _is_container_runtime() -> bool:
    if os.path.exists("/.dockerenv"):
        return True
    cgroup_path = Path("/proc/1/cgroup")
    if cgroup_path.exists():
        try:
            content = cgroup_path.read_text(encoding="utf-8", errors="ignore")
            lowered = content.lower()
            return "docker" in lowered or "containerd" in lowered or "kubepods" in lowered
        except Exception:
            return False
    return False


def _detect_mode() -> str:
    mode = os.environ.get("SKILL_RUNNER_RUNTIME_MODE", "").strip().lower()
    if mode in {"container", "local"}:
        return mode
    return "container" if _is_container_runtime() else "local"


def _local_base_dir() -> Path:
    system = platform.system().lower()
    if system == "windows":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "SkillRunner"
        return Path.home() / "AppData" / "Local" / "SkillRunner"
    if system == "darwin":
        return Path.home() / "Library" / "Application Support" / "SkillRunner"
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / "skill-runner"
    return Path.home() / ".local" / "share" / "skill-runner"


def _platform_name() -> str:
    system = platform.system().lower()
    if system.startswith("win"):
        return "windows"
    if system == "darwin":
        return "darwin"
    return "linux"


@dataclass(frozen=True)
class RuntimeProfile:
    mode: str
    platform: str
    data_dir: Path
    agent_cache_root: Path
    agent_home: Path
    npm_prefix: Path
    uv_cache_dir: Path
    uv_project_environment: Path

    @property
    def managed_bin_dirs(self) -> list[Path]:
        if self.platform == "windows":
            return [self.npm_prefix, self.npm_prefix / "bin", self.npm_prefix / "Scripts"]
        return [self.npm_prefix / "bin", self.npm_prefix]

    def ensure_directories(self, extra_dirs: Iterable[Path] = ()) -> None:
        targets = [
            self.data_dir,
            self.agent_cache_root,
            self.agent_home,
            self.npm_prefix,
            self.uv_cache_dir,
            self.uv_project_environment,
            *extra_dirs,
        ]
        for target in targets:
            target.mkdir(parents=True, exist_ok=True)

    def build_subprocess_env(self, base_env: Dict[str, str] | None = None) -> Dict[str, str]:
        env: Dict[str, str] = dict(base_env or os.environ)
        env["SKILL_RUNNER_RUNTIME_MODE"] = self.mode
        env["SKILL_RUNNER_DATA_DIR"] = str(self.data_dir)
        env["SKILL_RUNNER_AGENT_CACHE_DIR"] = str(self.agent_cache_root)
        env["SKILL_RUNNER_AGENT_HOME"] = str(self.agent_home)
        env["SKILL_RUNNER_NPM_PREFIX"] = str(self.npm_prefix)
        env["NPM_CONFIG_PREFIX"] = str(self.npm_prefix)
        env["UV_CACHE_DIR"] = str(self.uv_cache_dir)
        env["UV_PROJECT_ENVIRONMENT"] = str(self.uv_project_environment)
        xdg_config_home = self.agent_home / ".config"
        xdg_data_home = self.agent_home / ".local" / "share"
        xdg_state_home = self.agent_home / ".local" / "state"
        xdg_cache_home = self.agent_home / ".cache"
        env["XDG_CONFIG_HOME"] = str(xdg_config_home)
        env["XDG_DATA_HOME"] = str(xdg_data_home)
        env["XDG_STATE_HOME"] = str(xdg_state_home)
        env["XDG_CACHE_HOME"] = str(xdg_cache_home)
        if self.platform == "windows":
            env["USERPROFILE"] = str(self.agent_home)
            env["HOME"] = str(self.agent_home)
        else:
            env["HOME"] = str(self.agent_home)
            env["ZDOTDIR"] = str(self.agent_home)
        existing_path = env.get("PATH", "")
        prepend = os.pathsep.join(str(path) for path in self.managed_bin_dirs)
        env["PATH"] = f"{prepend}{os.pathsep}{existing_path}" if existing_path else prepend
        return env


@lru_cache(maxsize=1)
def get_runtime_profile() -> RuntimeProfile:
    mode = _detect_mode()
    platform_name = _platform_name()
    if mode == "container":
        cache_root_default = Path("/opt/cache/skill-runner")
        data_dir_default = Path("/data")
    else:
        base_dir = _local_base_dir()
        cache_root_default = base_dir / "agent-cache"
        data_dir_default = Path(config.SYSTEM.DATA_DIR)

    data_dir = Path(os.environ.get("SKILL_RUNNER_DATA_DIR", str(data_dir_default))).resolve()
    cache_root = Path(
        os.environ.get("SKILL_RUNNER_AGENT_CACHE_DIR", str(cache_root_default))
    ).resolve()
    agent_home = Path(
        os.environ.get("SKILL_RUNNER_AGENT_HOME", str(cache_root / "agent-home"))
    ).resolve()
    npm_prefix = Path(
        os.environ.get(
            "SKILL_RUNNER_NPM_PREFIX",
            os.environ.get("NPM_CONFIG_PREFIX", str(cache_root / "npm")),
        )
    ).resolve()
    uv_cache = Path(
        os.environ.get("UV_CACHE_DIR", str(cache_root / "uv_cache"))
    ).resolve()
    uv_venv = Path(
        os.environ.get("UV_PROJECT_ENVIRONMENT", str(cache_root / "uv_venv"))
    ).resolve()

    return RuntimeProfile(
        mode=mode,
        platform=platform_name,
        data_dir=data_dir,
        agent_cache_root=cache_root,
        agent_home=agent_home,
        npm_prefix=npm_prefix,
        uv_cache_dir=uv_cache,
        uv_project_environment=uv_venv,
    )


def reset_runtime_profile_cache() -> None:
    get_runtime_profile.cache_clear()
