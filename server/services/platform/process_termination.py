from __future__ import annotations

import asyncio
import os
import platform
import signal
import subprocess
import time
from dataclasses import dataclass
from typing import Literal

from server.config import config

TerminationOutcome = Literal["already_exited", "terminated", "failed"]
PopenProcess = subprocess.Popen[str] | subprocess.Popen[bytes]


@dataclass(frozen=True)
class TerminationResult:
    outcome: TerminationOutcome
    detail: str


def _term_grace(term_grace_sec: float | None) -> float:
    if term_grace_sec is not None:
        return max(0.1, float(term_grace_sec))
    return max(0.1, float(config.SYSTEM.PROCESS_TERMINATE_GRACE_SEC))


def _kill_grace(kill_grace_sec: float | None) -> float:
    if kill_grace_sec is not None:
        return max(0.1, float(kill_grace_sec))
    return max(0.1, float(config.SYSTEM.PROCESS_KILL_GRACE_SEC))


def _is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def terminate_pid_tree(
    pid: int,
    *,
    term_grace_sec: float | None = None,
    kill_grace_sec: float | None = None,
) -> TerminationResult:
    if pid <= 0:
        return TerminationResult(outcome="failed", detail="invalid_pid")
    if not _is_pid_alive(pid):
        return TerminationResult(outcome="already_exited", detail="pid_not_alive")

    if platform.system().lower().startswith("win"):
        try:
            result = subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True,
                text=True,
                check=False,
            )
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            return TerminationResult(outcome="failed", detail=f"taskkill_error:{type(exc).__name__}")
        if result.returncode == 0:
            return TerminationResult(outcome="terminated", detail="taskkill_ok")
        if not _is_pid_alive(pid):
            return TerminationResult(outcome="terminated", detail="taskkill_nonzero_but_exited")
        return TerminationResult(outcome="failed", detail=f"taskkill_rc:{result.returncode}")

    term_grace = _term_grace(term_grace_sec)
    kill_grace = _kill_grace(kill_grace_sec)
    killpg = getattr(os, "killpg", None)
    if not callable(killpg):
        return TerminationResult(outcome="failed", detail="killpg_unavailable")

    try:
        killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        return TerminationResult(outcome="already_exited", detail="pg_not_found")
    except OSError as exc:
        return TerminationResult(outcome="failed", detail=f"sigterm_error:{type(exc).__name__}")

    deadline = time.monotonic() + term_grace
    while time.monotonic() < deadline:
        if not _is_pid_alive(pid):
            return TerminationResult(outcome="terminated", detail="sigterm_ok")
        time.sleep(0.05)

    try:
        sigkill = getattr(signal, "SIGKILL", signal.SIGTERM)
        killpg(pid, sigkill)
    except ProcessLookupError:
        return TerminationResult(outcome="terminated", detail="sigkill_lookup_after_term")
    except OSError as exc:
        return TerminationResult(outcome="failed", detail=f"sigkill_error:{type(exc).__name__}")

    deadline = time.monotonic() + kill_grace
    while time.monotonic() < deadline:
        if not _is_pid_alive(pid):
            return TerminationResult(outcome="terminated", detail="sigkill_ok")
        time.sleep(0.05)
    if not _is_pid_alive(pid):
        return TerminationResult(outcome="terminated", detail="sigkill_eventual")
    return TerminationResult(outcome="failed", detail="pid_alive_after_sigkill")


async def terminate_asyncio_process_tree(
    proc: asyncio.subprocess.Process,
    *,
    term_grace_sec: float | None = None,
    kill_grace_sec: float | None = None,
) -> TerminationResult:
    if proc.returncode is not None:
        return TerminationResult(outcome="already_exited", detail="returncode_present")

    term_grace = _term_grace(term_grace_sec)
    kill_grace = _kill_grace(kill_grace_sec)

    if platform.system().lower().startswith("win"):
        try:
            proc.terminate()
            await asyncio.wait_for(proc.wait(), timeout=term_grace)
            return TerminationResult(outcome="terminated", detail="terminate_ok")
        except asyncio.TimeoutError:
            pass
        except (OSError, ValueError, RuntimeError) as exc:
            return TerminationResult(outcome="failed", detail=f"terminate_error:{type(exc).__name__}")

        try:
            proc.kill()
            await asyncio.wait_for(proc.wait(), timeout=kill_grace)
            return TerminationResult(outcome="terminated", detail="kill_ok")
        except asyncio.TimeoutError:
            return TerminationResult(outcome="failed", detail="timeout_after_kill")
        except (OSError, ValueError, RuntimeError) as exc:
            return TerminationResult(outcome="failed", detail=f"kill_error:{type(exc).__name__}")

    pid = proc.pid
    if pid <= 0:
        return TerminationResult(outcome="failed", detail="invalid_pid")

    getpgid = getattr(os, "getpgid", None)
    try:
        pgid = getpgid(pid) if callable(getpgid) else None
    except (OSError, ValueError):
        pgid = None

    killpg = getattr(os, "killpg", None)
    if pgid is not None and pgid == pid and callable(killpg):
        try:
            killpg(pgid, signal.SIGTERM)
            await asyncio.wait_for(proc.wait(), timeout=term_grace)
            return TerminationResult(outcome="terminated", detail="sigterm_ok")
        except asyncio.TimeoutError:
            pass
        except ProcessLookupError:
            return TerminationResult(outcome="already_exited", detail="process_lookup_sigterm")
        except OSError as exc:
            return TerminationResult(outcome="failed", detail=f"sigterm_error:{type(exc).__name__}")

        try:
            sigkill = getattr(signal, "SIGKILL", signal.SIGTERM)
            killpg(pgid, sigkill)
            await asyncio.wait_for(proc.wait(), timeout=kill_grace)
            return TerminationResult(outcome="terminated", detail="sigkill_ok")
        except asyncio.TimeoutError:
            return TerminationResult(outcome="failed", detail="timeout_after_sigkill")
        except ProcessLookupError:
            return TerminationResult(outcome="terminated", detail="process_lookup_sigkill")
        except OSError as exc:
            return TerminationResult(outcome="failed", detail=f"sigkill_error:{type(exc).__name__}")

    try:
        proc.terminate()
        await asyncio.wait_for(proc.wait(), timeout=term_grace)
        return TerminationResult(outcome="terminated", detail="fallback_terminate_ok")
    except asyncio.TimeoutError:
        pass
    except (OSError, ValueError, RuntimeError) as exc:
        return TerminationResult(outcome="failed", detail=f"fallback_terminate_error:{type(exc).__name__}")

    try:
        proc.kill()
        await asyncio.wait_for(proc.wait(), timeout=kill_grace)
        return TerminationResult(outcome="terminated", detail="fallback_kill_ok")
    except asyncio.TimeoutError:
        return TerminationResult(outcome="failed", detail="timeout_after_fallback_kill")
    except (OSError, ValueError, RuntimeError) as exc:
        return TerminationResult(outcome="failed", detail=f"fallback_kill_error:{type(exc).__name__}")


def terminate_popen_process_tree(
    proc: PopenProcess,
    *,
    term_grace_sec: float | None = None,
    kill_grace_sec: float | None = None,
) -> TerminationResult:
    if proc.poll() is not None:
        return TerminationResult(outcome="already_exited", detail="poll_returned")
    return terminate_pid_tree(
        int(proc.pid),
        term_grace_sec=term_grace_sec,
        kill_grace_sec=kill_grace_sec,
    )
