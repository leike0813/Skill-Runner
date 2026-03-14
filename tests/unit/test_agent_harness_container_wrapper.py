from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.skipif(
    sys.platform.startswith("win"),
    reason="POSIX-only shell wrapper test",
)


def _write_fake_docker(tmp_path: Path, *, exec_exit_code: int = 0) -> Path:
    log_path = tmp_path / "docker_invocations.log"
    stdin_path = tmp_path / "docker_stdin.log"
    script_path = tmp_path / "docker"
    script_path.write_text(
        f"""#!/usr/bin/env sh
set -eu
printf '%s\\n' "$*" >> "{log_path}"
if [ "$1" = "compose" ] && [ "$2" = "version" ]; then
  exit 0
fi
if [ "$1" = "compose" ] && [ "$2" = "ps" ]; then
  printf 'api\\n'
  exit 0
fi
if [ "$1" = "compose" ] && [ "$2" = "exec" ]; then
  cat > "{stdin_path}"
  exit {exec_exit_code}
fi
exit 9
""",
        encoding="utf-8",
    )
    script_path.chmod(0o755)
    return script_path


def test_agent_harness_container_wrapper_uses_non_tty_exec_and_forwards_args_and_stdin(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    wrapper = repo_root / "scripts" / "agent_harness_container.sh"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_fake_docker(fake_bin)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"

    result = subprocess.run(
        [str(wrapper), "start", "codex", "--json", "--full-auto", "hello"],
        input="stdin-payload",
        text=True,
        capture_output=True,
        env=env,
        cwd=str(repo_root),
        check=False,
    )

    assert result.returncode == 0
    invocations = (fake_bin / "docker_invocations.log").read_text(encoding="utf-8").splitlines()
    assert invocations[0] == "compose version"
    assert invocations[1] == "compose ps --status running --services"
    assert invocations[2] == "compose exec -T api agent-harness start codex --json --full-auto hello"
    assert (fake_bin / "docker_stdin.log").read_text(encoding="utf-8") == "stdin-payload"


def test_agent_harness_container_wrapper_fails_when_api_is_not_running(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    wrapper = repo_root / "scripts" / "agent_harness_container.sh"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    docker_path = fake_bin / "docker"
    docker_path.write_text(
        """#!/usr/bin/env sh
set -eu
if [ "$1" = "compose" ] && [ "$2" = "version" ]; then
  exit 0
fi
if [ "$1" = "compose" ] && [ "$2" = "ps" ]; then
  exit 0
fi
exit 9
""",
        encoding="utf-8",
    )
    docker_path.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"

    result = subprocess.run(
        [str(wrapper), "start", "codex"],
        text=True,
        capture_output=True,
        env=env,
        cwd=str(repo_root),
        check=False,
    )

    assert result.returncode == 1
    assert "service 'api' is not running" in result.stdout
