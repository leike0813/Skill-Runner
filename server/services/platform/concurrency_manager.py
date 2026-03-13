import asyncio
import ctypes
import ctypes.wintypes as wintypes
import logging
import os
import platform
import threading
from pathlib import Path
from typing import Any, Dict

from server.config import config

try:
    import psutil  # type: ignore[import-untyped]
except ImportError:
    psutil = None  # type: ignore[assignment]

try:
    import resource
except ImportError:  # pragma: no cover - Windows has no resource module
    resource = None  # type: ignore[assignment]


class _WindowsConcurrencyProbeFatal(RuntimeError):
    """Fatal probe error on Windows; caller should fail fast."""


class ConcurrencyManager:
    """
    Global concurrency guard for CLI process execution.

    Behavior:
    - Admits requests into a bounded queue.
    - Moves queued tasks into running slots via a semaphore.
    - Rejects new requests with queue-full signal when queue is saturated.
    """

    def __init__(self) -> None:
        self._initialized = False
        self._semaphore: asyncio.Semaphore | None = None
        self._state_lock = threading.Lock()
        self._running = 0
        self._queued = 0
        self._max_concurrent = 1
        self._max_queue_size = 1
        self._policy: Dict[str, Any] = {}
        self._loop_id: int | None = None

    def start(self) -> None:
        if self._initialized:
            return

        try:
            policy = self._load_policy()
            self._max_concurrent = self._compute_max_concurrency(policy)
            self._max_queue_size = max(1, int(policy["max_queue_size"]))
            self._policy = policy
        except (OSError, ValueError, TypeError, KeyError):
            logger.exception("Failed to initialize concurrency policy, using fallback defaults")
            self._max_concurrent = 2
            self._max_queue_size = 128
            self._policy = {"fallback": True}

        self._semaphore = asyncio.Semaphore(self._max_concurrent)
        self._initialized = True
        logger.info(
            "Concurrency manager initialized: max_concurrent=%s max_queue_size=%s",
            self._max_concurrent,
            self._max_queue_size,
        )

    async def admit_or_reject(self) -> bool:
        self.start()
        self._ensure_loop()
        with self._state_lock:
            if self._queued >= self._max_queue_size:
                return False
            self._queued += 1
            return True

    async def acquire_slot(self) -> None:
        self.start()
        self._ensure_loop()
        with self._state_lock:
            if self._queued > 0:
                self._queued -= 1
        if self._semaphore is None:
            raise RuntimeError("Concurrency manager not initialized")
        await self._semaphore.acquire()
        with self._state_lock:
            self._running += 1

    async def release_slot(self) -> None:
        if self._semaphore is None:
            return
        self._ensure_loop()
        with self._state_lock:
            if self._running > 0:
                self._running -= 1
        self._semaphore.release()

    async def state(self) -> Dict[str, int]:
        with self._state_lock:
            return {
                "running": self._running,
                "queued": self._queued,
                "max_concurrent": self._max_concurrent,
                "max_queue_size": self._max_queue_size,
            }

    def reset_runtime_state(self) -> None:
        self.start()
        with self._state_lock:
            self._running = 0
            self._queued = 0
            self._semaphore = asyncio.Semaphore(self._max_concurrent)
            self._loop_id = None

    def _ensure_loop(self) -> None:
        """
        Recreate semaphore when running on a different event loop.
        This keeps test isolation stable under pytest-asyncio.
        """
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        current_id = id(current_loop)
        if self._loop_id is None:
            self._loop_id = current_id
            return
        if self._loop_id != current_id:
            self._semaphore = asyncio.Semaphore(self._max_concurrent)
            self._running = 0
            self._queued = 0
            self._loop_id = current_id

    def _load_policy(self) -> Dict[str, Any]:
        cfg = config.SYSTEM.CONCURRENCY
        policy: Dict[str, Any] = {
            "max_concurrent_hard_cap": int(cfg.MAX_CONCURRENT_HARD_CAP),
            "max_queue_size": int(cfg.MAX_QUEUE_SIZE),
            "cpu_factor": float(cfg.CPU_FACTOR),
            "mem_reserve_mb": int(cfg.MEM_RESERVE_MB),
            "estimated_mem_per_run_mb": int(cfg.ESTIMATED_MEM_PER_RUN_MB),
            "fd_reserve": int(cfg.FD_RESERVE),
            "estimated_fd_per_run": int(cfg.ESTIMATED_FD_PER_RUN),
            "pid_reserve": int(cfg.PID_RESERVE),
            "estimated_pid_per_run": int(cfg.ESTIMATED_PID_PER_RUN),
            "fallback_max_concurrent": int(cfg.FALLBACK_MAX_CONCURRENT),
        }

        policy["max_concurrent_hard_cap"] = self._env_int(
            "SKILL_RUNNER_MAX_CONCURRENT_HARD_CAP",
            policy.get("max_concurrent_hard_cap", 16),
        )
        policy["max_queue_size"] = self._env_int(
            "SKILL_RUNNER_MAX_QUEUE_SIZE",
            policy.get("max_queue_size", 128),
        )
        policy["cpu_factor"] = self._env_float(
            "SKILL_RUNNER_CPU_FACTOR",
            policy.get("cpu_factor", 0.75),
        )
        policy["mem_reserve_mb"] = self._env_int(
            "SKILL_RUNNER_MEM_RESERVE_MB",
            policy.get("mem_reserve_mb", 1024),
        )
        policy["estimated_mem_per_run_mb"] = self._env_int(
            "SKILL_RUNNER_ESTIMATED_MEM_PER_RUN_MB",
            policy.get("estimated_mem_per_run_mb", 1024),
        )
        policy["fd_reserve"] = self._env_int(
            "SKILL_RUNNER_FD_RESERVE",
            policy.get("fd_reserve", 256),
        )
        policy["estimated_fd_per_run"] = self._env_int(
            "SKILL_RUNNER_ESTIMATED_FD_PER_RUN",
            policy.get("estimated_fd_per_run", 64),
        )
        policy["pid_reserve"] = self._env_int(
            "SKILL_RUNNER_PID_RESERVE",
            policy.get("pid_reserve", 128),
        )
        policy["estimated_pid_per_run"] = self._env_int(
            "SKILL_RUNNER_ESTIMATED_PID_PER_RUN",
            policy.get("estimated_pid_per_run", 1),
        )
        policy["fallback_max_concurrent"] = self._env_int(
            "SKILL_RUNNER_FALLBACK_MAX_CONCURRENT",
            policy.get("fallback_max_concurrent", 2),
        )
        return policy

    def _compute_max_concurrency(self, policy: Dict[str, Any]) -> int:
        fallback = max(1, int(policy["fallback_max_concurrent"]))
        try:
            cpu_count = os.cpu_count() or 1
            cpu_limit = max(1, int(cpu_count * float(policy["cpu_factor"])))

            mem_available_mb = self._mem_available_mb()
            mem_budget = max(1, mem_available_mb - int(policy["mem_reserve_mb"]))
            mem_limit = max(1, mem_budget // max(1, int(policy["estimated_mem_per_run_mb"])))
            hard_cap = max(1, int(policy["max_concurrent_hard_cap"]))

            if self._is_windows():
                fd_limit = self._windows_fd_limit(policy, hard_cap)
                pid_limit = self._windows_pid_limit(policy, hard_cap)
            else:
                getrlimit = getattr(resource, "getrlimit", None)
                rlimit_nofile = getattr(resource, "RLIMIT_NOFILE", None)
                rlimit_nproc = getattr(resource, "RLIMIT_NPROC", None)
                if (
                    getrlimit is None
                    or rlimit_nofile is None
                    or rlimit_nproc is None
                ):
                    fd_limit = int(policy["max_concurrent_hard_cap"])
                    pid_limit = int(policy["max_concurrent_hard_cap"])
                else:
                    fd_soft, _ = getrlimit(rlimit_nofile)
                    fd_budget = max(1, int(fd_soft) - int(policy["fd_reserve"]))
                    fd_limit = max(1, fd_budget // max(1, int(policy["estimated_fd_per_run"])))

                    nproc_soft, _ = getrlimit(rlimit_nproc)
                    if nproc_soft < 0:
                        pid_limit = int(policy["max_concurrent_hard_cap"])
                    else:
                        pid_budget = max(1, int(nproc_soft) - int(policy["pid_reserve"]))
                        pid_limit = max(1, pid_budget // max(1, int(policy["estimated_pid_per_run"])))

            limit = min(cpu_limit, mem_limit, fd_limit, pid_limit, hard_cap)
            return max(1, limit)
        except _WindowsConcurrencyProbeFatal:
            raise
        except (OSError, ValueError, TypeError, KeyError, RuntimeError):
            logger.exception("Resource probe failed, using fallback concurrency")
            return fallback

    def _is_windows(self) -> bool:
        return platform.system().lower().startswith("win")

    def _mem_available_mb(self) -> int:
        if self._is_windows():
            return self._windows_mem_available_mb()
        meminfo = Path("/proc/meminfo")
        if not meminfo.exists():
            raise RuntimeError("/proc/meminfo not found")
        for line in meminfo.read_text(encoding="utf-8").splitlines():
            if line.startswith("MemAvailable:"):
                parts = line.split()
                kb = int(parts[1])
                return max(1, kb // 1024)
        raise RuntimeError("MemAvailable not found")

    def _windows_mem_available_mb(self) -> int:
        if psutil is None:
            raise _WindowsConcurrencyProbeFatal(
                "psutil is required on Windows for concurrency probe; install project dependencies."
            )
        try:
            available = int(psutil.virtual_memory().available // 1024 // 1024)
        except Exception as exc:  # pragma: no cover - guarded by tests via monkeypatch
            raise _WindowsConcurrencyProbeFatal(
                f"failed to probe Windows available memory via psutil: {type(exc).__name__}"
            ) from exc
        if available <= 0:
            raise _WindowsConcurrencyProbeFatal("invalid Windows available memory probe result")
        return available

    def _windows_fd_limit(self, policy: Dict[str, Any], hard_cap: int) -> int:
        max_stdio = self._windows_max_stdio()
        fd_budget = max(1, max_stdio - int(policy["fd_reserve"]))
        return max(1, fd_budget // max(1, int(policy["estimated_fd_per_run"])))

    def _windows_pid_limit(self, policy: Dict[str, Any], hard_cap: int) -> int:
        active_limit = self._windows_active_process_limit()
        if active_limit is None:
            return hard_cap
        pid_budget = max(1, active_limit - int(policy["pid_reserve"]))
        return max(1, pid_budget // max(1, int(policy["estimated_pid_per_run"])))

    def _windows_max_stdio(self) -> int:
        last_error: Exception | None = None
        for dll_name in ("ucrtbase", "msvcrt"):
            try:
                crt = ctypes.CDLL(dll_name)
                getter = getattr(crt, "_getmaxstdio", None)
                if getter is None:
                    continue
                getter.restype = ctypes.c_int
                value = int(getter())
                if value > 0:
                    return value
                last_error = RuntimeError(f"_getmaxstdio from {dll_name} returned non-positive value")
            except (AttributeError, OSError, TypeError, ValueError) as exc:
                last_error = exc
        raise _WindowsConcurrencyProbeFatal(
            "failed to probe Windows stdio upper bound via _getmaxstdio"
        ) from last_error

    def _windows_active_process_limit(self) -> int | None:
        job_object_extended_limit_information = 9
        job_object_limit_active_process = 0x00000008

        class _IoCounters(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_ulonglong),
                ("WriteOperationCount", ctypes.c_ulonglong),
                ("OtherOperationCount", ctypes.c_ulonglong),
                ("ReadTransferCount", ctypes.c_ulonglong),
                ("WriteTransferCount", ctypes.c_ulonglong),
                ("OtherTransferCount", ctypes.c_ulonglong),
            ]

        class _JobObjectBasicLimitInformation(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_longlong),
                ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class _JobObjectExtendedLimitInformation(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", _JobObjectBasicLimitInformation),
                ("IoInfo", _IoCounters),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        except OSError as exc:  # pragma: no cover - Windows runtime only
            raise _WindowsConcurrencyProbeFatal("failed to load kernel32 for job limit probe") from exc

        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        kernel32.GetCurrentProcess.argtypes = []
        kernel32.IsProcessInJob.restype = wintypes.BOOL
        kernel32.IsProcessInJob.argtypes = [
            wintypes.HANDLE,
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.BOOL),
        ]
        kernel32.QueryInformationJobObject.restype = wintypes.BOOL
        kernel32.QueryInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
        ]

        current_process = kernel32.GetCurrentProcess()
        if not current_process:
            raise _WindowsConcurrencyProbeFatal("GetCurrentProcess failed during job limit probe")

        in_job = wintypes.BOOL()
        if not kernel32.IsProcessInJob(current_process, None, ctypes.byref(in_job)):
            err_code = ctypes.get_last_error()
            raise _WindowsConcurrencyProbeFatal(f"IsProcessInJob failed with code={err_code}")
        if not bool(in_job.value):
            return None

        info = _JobObjectExtendedLimitInformation()
        returned_length = wintypes.DWORD()
        ok = kernel32.QueryInformationJobObject(
            None,
            job_object_extended_limit_information,
            ctypes.byref(info),
            ctypes.sizeof(info),
            ctypes.byref(returned_length),
        )
        if not ok:
            err_code = ctypes.get_last_error()
            raise _WindowsConcurrencyProbeFatal(
                f"QueryInformationJobObject failed with code={err_code}"
            )

        flags = int(info.BasicLimitInformation.LimitFlags)
        active_limit = int(info.BasicLimitInformation.ActiveProcessLimit)
        if (flags & job_object_limit_active_process) and active_limit > 0:
            return active_limit
        return None

    def _env_int(self, key: str, default: int) -> int:
        raw = os.environ.get(key)
        if raw is None:
            return int(default)
        try:
            return int(raw)
        except ValueError:
            logger.warning("Invalid integer env %s=%s, fallback to %s", key, raw, default)
            return int(default)

    def _env_float(self, key: str, default: float) -> float:
        raw = os.environ.get(key)
        if raw is None:
            return float(default)
        try:
            return float(raw)
        except ValueError:
            logger.warning("Invalid float env %s=%s, fallback to %s", key, raw, default)
            return float(default)


concurrency_manager = ConcurrencyManager()

logger = logging.getLogger(__name__)
