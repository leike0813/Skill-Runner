from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


POSIX_ONLY = pytest.mark.skipif(sys.platform.startswith("win"), reason="POSIX-only shell script tests")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read_script(rel_path: str) -> str:
    return (_repo_root() / rel_path).read_text(encoding="utf-8")


def _prepare_local_root(base_dir: Path) -> Path:
    local_root = base_dir / "local-root"
    (local_root / "releases").mkdir(parents=True)
    (local_root / "agent-cache" / "npm").mkdir(parents=True)
    (local_root / "agent-cache" / "uv_cache").mkdir(parents=True)
    (local_root / "agent-cache" / "uv_venv").mkdir(parents=True)
    (local_root / "agent-cache" / "agent-home").mkdir(parents=True)
    (local_root / "data").mkdir(parents=True)
    return local_root


def _write_ctl_stub(base_dir: Path, *, exit_code: int = 0) -> tuple[Path, Path]:
    log_path = base_dir / "ctl_invocations.log"
    stub_path = base_dir / "skill-runnerctl"
    stub_path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env sh",
                "set -eu",
                f'printf "%s\\n" "$*" >> "{log_path}"',
                'printf \'{"ok":true,"from":"stub"}\\n\'',
                f"exit {exit_code}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    stub_path.chmod(0o755)
    return stub_path, log_path


@POSIX_ONLY
def test_skill_runnerctl_wrappers_and_uninstall_scripts_expose_contract_fields() -> None:
    shell_ctl = _read_script("scripts/skill-runnerctl")
    ps_ctl = _read_script("scripts/skill-runnerctl.ps1")
    shell_uninstall = _read_script("scripts/skill-runner-uninstall.sh")
    ps_uninstall = _read_script("scripts/skill-runner-uninstall.ps1")

    assert 'SKILL_RUNNER_DATA_DIR="${SKILL_RUNNER_DATA_DIR:-$LOCAL_ROOT/data}"' in shell_ctl
    assert 'SKILL_RUNNER_LOCAL_PORT="${SKILL_RUNNER_LOCAL_PORT:-29813}"' in shell_ctl
    assert 'SKILL_RUNNER_LOCAL_PORT_FALLBACK_SPAN="${SKILL_RUNNER_LOCAL_PORT_FALLBACK_SPAN:-10}"' in shell_ctl
    assert 'Join-Path $LocalRoot "data"' in ps_ctl
    assert 'SKILL_RUNNER_LOCAL_PORT = if ($env:SKILL_RUNNER_LOCAL_PORT)' in ps_ctl
    assert "SKILL_RUNNER_LOCAL_PORT_FALLBACK_SPAN" in ps_ctl

    assert "--clear-data)" in shell_uninstall
    assert "--clear-agent-home)" in shell_uninstall
    assert "--json)" in shell_uninstall
    assert "--local-root)" in shell_uninstall
    assert '"removed_paths":%s' in shell_uninstall
    assert '"failed_paths":%s' in shell_uninstall
    assert '"preserved_paths":%s' in shell_uninstall
    assert '"down_result":{"invoked":true' in shell_uninstall

    assert "[switch]$ClearData" in ps_uninstall
    assert "[switch]$ClearAgentHome" in ps_uninstall
    assert "[switch]$Json" in ps_uninstall
    assert "[string]$LocalRoot" in ps_uninstall
    assert "removed_paths" in ps_uninstall
    assert "failed_paths" in ps_uninstall
    assert "preserved_paths" in ps_uninstall
    assert "down_result" in ps_uninstall


def _run_uninstall(
    tmp_path: Path,
    *,
    clear_data: bool = False,
    clear_agent_home: bool = False,
    ctl_exit_code: int = 0,
    path_prefix: str | None = None,
) -> tuple[subprocess.CompletedProcess[str], dict[str, object], Path, Path]:
    local_root = _prepare_local_root(tmp_path)
    ctl_stub, ctl_log = _write_ctl_stub(tmp_path, exit_code=ctl_exit_code)
    script_path = _repo_root() / "scripts" / "skill-runner-uninstall.sh"

    cmd = ["sh", str(script_path), "--json", "--local-root", str(local_root)]
    if clear_data:
        cmd.append("--clear-data")
    if clear_agent_home:
        cmd.append("--clear-agent-home")

    env = os.environ.copy()
    env["SKILL_RUNNER_CTL_PATH"] = str(ctl_stub)
    if path_prefix:
        env["PATH"] = f"{path_prefix}:{env.get('PATH', '')}"

    result = subprocess.run(
        cmd,
        text=True,
        capture_output=True,
        cwd=str(_repo_root()),
        env=env,
        check=False,
    )
    payload = json.loads(result.stdout.strip())
    return result, payload, local_root, ctl_log


@POSIX_ONLY
def test_shell_ctl_wrapper_defaults_data_dir_to_local_root(tmp_path: Path) -> None:
    repo_root = _repo_root()
    wrapper = repo_root / "scripts" / "skill-runnerctl"
    local_root = tmp_path / "local-root"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    env_log = tmp_path / "uv_env.log"
    arg_log = tmp_path / "uv_args.log"

    fake_uv = fake_bin / "uv"
    fake_uv.write_text(
        "\n".join(
            [
                "#!/usr/bin/env sh",
                "set -eu",
                f'printf "%s\\n" "$SKILL_RUNNER_DATA_DIR" > "{env_log}"',
                f'printf "%s\\n" "$*" > "{arg_log}"',
                "exit 0",
                "",
            ]
        ),
        encoding="utf-8",
    )
    fake_uv.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["SKILL_RUNNER_LOCAL_ROOT"] = str(local_root)
    env.pop("SKILL_RUNNER_DATA_DIR", None)

    result = subprocess.run(
        ["sh", str(wrapper), "doctor", "--json"],
        text=True,
        capture_output=True,
        cwd=str(repo_root),
        env=env,
        check=False,
    )

    assert result.returncode == 0
    assert env_log.read_text(encoding="utf-8").strip() == str(local_root / "data")
    assert arg_log.read_text(encoding="utf-8").strip() == "run python scripts/skill_runnerctl.py doctor --json"


@POSIX_ONLY
def test_uninstall_default_mode_keeps_data_and_agent_home(tmp_path: Path) -> None:
    result, payload, local_root, ctl_log = _run_uninstall(tmp_path)

    assert result.returncode == 0
    assert payload["ok"] is True
    assert (local_root / "releases").exists() is False
    assert (local_root / "agent-cache" / "npm").exists() is False
    assert (local_root / "agent-cache" / "uv_cache").exists() is False
    assert (local_root / "agent-cache" / "uv_venv").exists() is False
    assert (local_root / "data").exists() is True
    assert (local_root / "agent-cache" / "agent-home").exists() is True
    assert ctl_log.read_text(encoding="utf-8").splitlines() == ["down --mode local --json"]


@POSIX_ONLY
def test_uninstall_continues_cleanup_when_down_fails(tmp_path: Path) -> None:
    result, payload, local_root, _ = _run_uninstall(tmp_path, ctl_exit_code=7)

    assert result.returncode == 0
    assert payload["ok"] is True
    down_result = payload["down_result"]
    assert isinstance(down_result, dict)
    assert down_result["ok"] is False
    assert down_result["exit_code"] == 7
    assert (local_root / "releases").exists() is False


@POSIX_ONLY
def test_uninstall_clear_data_mode(tmp_path: Path) -> None:
    result, payload, local_root, _ = _run_uninstall(tmp_path, clear_data=True)

    assert result.returncode == 0
    assert payload["ok"] is True
    assert (local_root / "data").exists() is False
    assert (local_root / "agent-cache" / "agent-home").exists() is True


@POSIX_ONLY
def test_uninstall_clear_agent_home_mode(tmp_path: Path) -> None:
    result, payload, local_root, _ = _run_uninstall(tmp_path, clear_agent_home=True)

    assert result.returncode == 0
    assert payload["ok"] is True
    assert (local_root / "data").exists() is True
    assert (local_root / "agent-cache" / "agent-home").exists() is False


@POSIX_ONLY
def test_uninstall_clear_data_and_agent_home_attempts_remove_local_root(tmp_path: Path) -> None:
    result, payload, local_root, _ = _run_uninstall(tmp_path, clear_data=True, clear_agent_home=True)

    assert result.returncode == 0
    assert payload["ok"] is True
    assert local_root.exists() is False


@POSIX_ONLY
def test_uninstall_reports_failed_paths_and_non_zero_exit_on_delete_failure(tmp_path: Path) -> None:
    real_rm = shutil.which("rm")
    assert real_rm is not None

    local_root = _prepare_local_root(tmp_path)
    fail_path = local_root / "agent-cache" / "uv_venv"
    ctl_stub, _ = _write_ctl_stub(tmp_path)

    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    fake_rm = fake_bin / "rm"
    fake_rm.write_text(
        "\n".join(
            [
                "#!/usr/bin/env sh",
                "set -eu",
                f'if [ "$#" -ge 2 ] && [ "$1" = "-rf" ] && [ "$2" = "{fail_path}" ]; then',
                "  exit 1",
                "fi",
                f'exec "{real_rm}" "$@"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    fake_rm.chmod(0o755)

    script_path = _repo_root() / "scripts" / "skill-runner-uninstall.sh"
    env = os.environ.copy()
    env["SKILL_RUNNER_CTL_PATH"] = str(ctl_stub)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"

    result = subprocess.run(
        ["sh", str(script_path), "--json", "--local-root", str(local_root)],
        text=True,
        capture_output=True,
        cwd=str(_repo_root()),
        env=env,
        check=False,
    )

    payload = json.loads(result.stdout.strip())
    assert result.returncode == 1
    assert payload["ok"] is False
    assert payload["exit_code"] == 1
    failed_paths = set(payload["failed_paths"])
    assert str(fail_path) in failed_paths
