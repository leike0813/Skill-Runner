from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path
from typing import Any, Protocol


class ProcessHandle(Protocol):
    @property
    def pid(self) -> int:
        ...

    def poll(self) -> int | None:
        ...


class CliPtyRuntime(Protocol):
    process: ProcessHandle
    master_fd: int

    def read(self, size: int) -> bytes:
        ...

    def write(self, text: str) -> None:
        ...

    def close(self) -> None:
        ...


def _is_windows() -> bool:
    return platform.system().lower().startswith("win")


def detect_pywinpty_support() -> tuple[bool, str | None]:
    if not _is_windows():
        return True, None
    try:
        import winpty  # type: ignore[import-not-found]
    except (ImportError, OSError) as exc:
        return False, f"import_error:{type(exc).__name__}"
    pty_process_cls = getattr(winpty, "PtyProcess", None)
    spawn = getattr(pty_process_cls, "spawn", None) if pty_process_cls is not None else None
    if pty_process_cls is None or not callable(spawn):
        return False, "missing_PtyProcess_spawn"
    return True, None


class _PosixPtyRuntime:
    def __init__(self, *, process: subprocess.Popen[bytes], master_fd: int) -> None:
        self.process: ProcessHandle = process
        self.master_fd = master_fd
        self._closed = False

    def read(self, size: int) -> bytes:
        return os.read(self.master_fd, size)

    def write(self, text: str) -> None:
        os.write(self.master_fd, text.encode("utf-8", errors="replace"))

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        os.close(self.master_fd)


class _WinptyProcessHandle:
    def __init__(self, process: Any) -> None:
        self._process = process

    @property
    def pid(self) -> int:
        pid = getattr(self._process, "pid", 0)
        return int(pid) if isinstance(pid, int) else 0

    def poll(self) -> int | None:
        try:
            if bool(self._process.isalive()):
                return None
        except (OSError, RuntimeError, ValueError):
            return 1
        status = getattr(self._process, "exitstatus", None)
        if isinstance(status, int):
            return status
        return 0


class _WinptyRuntime:
    def __init__(self, process: Any) -> None:
        self._pty_process = process
        self.process: ProcessHandle = _WinptyProcessHandle(process)
        self.master_fd = -1
        self._closed = False

    def read(self, size: int) -> bytes:
        try:
            text = self._pty_process.read(size)
        except EOFError:
            return b""
        except (OSError, RuntimeError, ValueError) as exc:
            raise OSError(str(exc)) from exc
        if isinstance(text, bytes):
            return text
        return str(text).encode("utf-8", errors="replace")

    def write(self, text: str) -> None:
        try:
            self._pty_process.write(text)
        except (OSError, RuntimeError, ValueError) as exc:
            raise OSError(str(exc)) from exc

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._pty_process.close(force=True)
            return
        except TypeError:
            pass
        except (OSError, RuntimeError, ValueError):
            return
        try:
            self._pty_process.close()
        except (OSError, RuntimeError, ValueError):
            pass


def _open_pty_pair() -> tuple[int, int]:
    if hasattr(os, "openpty"):
        return os.openpty()
    import pty  # type: ignore[import-not-found]

    return pty.openpty()  # type: ignore[attr-defined]


def _spawn_posix_cli_pty(
    *,
    command: list[str],
    cwd: Path,
    env: dict[str, str],
) -> CliPtyRuntime:
    master_fd, slave_fd = _open_pty_pair()
    try:
        process = subprocess.Popen(
            command,
            cwd=str(cwd),
            env=env,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            text=False,
            start_new_session=True,
        )
    finally:
        try:
            os.close(slave_fd)
        except OSError:
            pass
    return _PosixPtyRuntime(process=process, master_fd=master_fd)


def _spawn_windows_cli_pty(
    *,
    command: list[str],
    cwd: Path,
    env: dict[str, str],
) -> CliPtyRuntime:
    ok, detail = detect_pywinpty_support()
    if not ok:
        reason = detail or "unknown_reason"
        raise RuntimeError(f"pywinpty unavailable: {reason}")
    import winpty  # type: ignore[import-not-found]

    process = winpty.PtyProcess.spawn(
        command,
        cwd=str(cwd),
        env=env,
    )
    return _WinptyRuntime(process)


def spawn_cli_pty(
    *,
    command: list[str],
    cwd: Path,
    env: dict[str, str],
) -> CliPtyRuntime:
    normalized = [str(part) for part in command]
    if _is_windows():
        return _spawn_windows_cli_pty(command=normalized, cwd=cwd, env=env)
    return _spawn_posix_cli_pty(command=normalized, cwd=cwd, env=env)
