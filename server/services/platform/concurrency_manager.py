import asyncio
import json
import logging
import os
import resource
import threading
from pathlib import Path
from typing import Any, Dict

from server.config import config


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
        except Exception:
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
        policy_path = Path(config.SYSTEM.CONCURRENCY_POLICY)
        with open(policy_path, "r", encoding="utf-8") as f:
            policy: Dict[str, Any] = json.load(f)

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

            fd_soft, _ = resource.getrlimit(resource.RLIMIT_NOFILE)
            fd_budget = max(1, int(fd_soft) - int(policy["fd_reserve"]))
            fd_limit = max(1, fd_budget // max(1, int(policy["estimated_fd_per_run"])))

            nproc_soft, _ = resource.getrlimit(resource.RLIMIT_NPROC)
            if nproc_soft < 0:
                pid_limit = int(policy["max_concurrent_hard_cap"])
            else:
                pid_budget = max(1, int(nproc_soft) - int(policy["pid_reserve"]))
                pid_limit = max(1, pid_budget // max(1, int(policy["estimated_pid_per_run"])))

            hard_cap = max(1, int(policy["max_concurrent_hard_cap"]))
            limit = min(cpu_limit, mem_limit, fd_limit, pid_limit, hard_cap)
            return max(1, limit)
        except Exception:
            logger.exception("Resource probe failed, using fallback concurrency")
            return fallback

    def _mem_available_mb(self) -> int:
        meminfo = Path("/proc/meminfo")
        if not meminfo.exists():
            raise RuntimeError("/proc/meminfo not found")
        for line in meminfo.read_text(encoding="utf-8").splitlines():
            if line.startswith("MemAvailable:"):
                parts = line.split()
                kb = int(parts[1])
                return max(1, kb // 1024)
        raise RuntimeError("MemAvailable not found")

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
