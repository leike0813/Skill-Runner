import asyncio

import pytest

from server.config import config
from server.services.platform import concurrency_manager as cm_module
from server.services.platform.concurrency_manager import ConcurrencyManager


@pytest.fixture
def temp_concurrency_profile():
    config.defrost()
    old_cfg = {
        "MAX_CONCURRENT_HARD_CAP": config.SYSTEM.CONCURRENCY.MAX_CONCURRENT_HARD_CAP,
        "MAX_QUEUE_SIZE": config.SYSTEM.CONCURRENCY.MAX_QUEUE_SIZE,
        "CPU_FACTOR": config.SYSTEM.CONCURRENCY.CPU_FACTOR,
        "MEM_RESERVE_MB": config.SYSTEM.CONCURRENCY.MEM_RESERVE_MB,
        "ESTIMATED_MEM_PER_RUN_MB": config.SYSTEM.CONCURRENCY.ESTIMATED_MEM_PER_RUN_MB,
        "FD_RESERVE": config.SYSTEM.CONCURRENCY.FD_RESERVE,
        "ESTIMATED_FD_PER_RUN": config.SYSTEM.CONCURRENCY.ESTIMATED_FD_PER_RUN,
        "PID_RESERVE": config.SYSTEM.CONCURRENCY.PID_RESERVE,
        "ESTIMATED_PID_PER_RUN": config.SYSTEM.CONCURRENCY.ESTIMATED_PID_PER_RUN,
        "FALLBACK_MAX_CONCURRENT": config.SYSTEM.CONCURRENCY.FALLBACK_MAX_CONCURRENT,
    }
    config.SYSTEM.CONCURRENCY.MAX_CONCURRENT_HARD_CAP = 16
    config.SYSTEM.CONCURRENCY.MAX_QUEUE_SIZE = 8
    config.SYSTEM.CONCURRENCY.CPU_FACTOR = 1.0
    config.SYSTEM.CONCURRENCY.MEM_RESERVE_MB = 256
    config.SYSTEM.CONCURRENCY.ESTIMATED_MEM_PER_RUN_MB = 256
    config.SYSTEM.CONCURRENCY.FD_RESERVE = 64
    config.SYSTEM.CONCURRENCY.ESTIMATED_FD_PER_RUN = 8
    config.SYSTEM.CONCURRENCY.PID_RESERVE = 16
    config.SYSTEM.CONCURRENCY.ESTIMATED_PID_PER_RUN = 1
    config.SYSTEM.CONCURRENCY.FALLBACK_MAX_CONCURRENT = 2
    config.freeze()
    try:
        yield
    finally:
        config.defrost()
        config.SYSTEM.CONCURRENCY.MAX_CONCURRENT_HARD_CAP = old_cfg["MAX_CONCURRENT_HARD_CAP"]
        config.SYSTEM.CONCURRENCY.MAX_QUEUE_SIZE = old_cfg["MAX_QUEUE_SIZE"]
        config.SYSTEM.CONCURRENCY.CPU_FACTOR = old_cfg["CPU_FACTOR"]
        config.SYSTEM.CONCURRENCY.MEM_RESERVE_MB = old_cfg["MEM_RESERVE_MB"]
        config.SYSTEM.CONCURRENCY.ESTIMATED_MEM_PER_RUN_MB = old_cfg["ESTIMATED_MEM_PER_RUN_MB"]
        config.SYSTEM.CONCURRENCY.FD_RESERVE = old_cfg["FD_RESERVE"]
        config.SYSTEM.CONCURRENCY.ESTIMATED_FD_PER_RUN = old_cfg["ESTIMATED_FD_PER_RUN"]
        config.SYSTEM.CONCURRENCY.PID_RESERVE = old_cfg["PID_RESERVE"]
        config.SYSTEM.CONCURRENCY.ESTIMATED_PID_PER_RUN = old_cfg["ESTIMATED_PID_PER_RUN"]
        config.SYSTEM.CONCURRENCY.FALLBACK_MAX_CONCURRENT = old_cfg["FALLBACK_MAX_CONCURRENT"]
        config.freeze()


def test_start_fallback_when_policy_invalid(monkeypatch):
    manager = ConcurrencyManager()
    monkeypatch.setattr(manager, "_load_policy", lambda: (_ for _ in ()).throw(ValueError("bad policy")))
    manager.start()
    assert manager._max_concurrent == 2
    assert manager._max_queue_size == 128


@pytest.mark.asyncio
async def test_admit_or_reject_queue_limit():
    manager = ConcurrencyManager()
    manager._initialized = True
    manager._max_queue_size = 1
    manager._max_concurrent = 1
    manager._semaphore = asyncio.Semaphore(1)

    admitted_first = await manager.admit_or_reject()
    admitted_second = await manager.admit_or_reject()

    assert admitted_first is True
    assert admitted_second is False


@pytest.mark.asyncio
async def test_acquire_and_release_slot_updates_state():
    manager = ConcurrencyManager()
    manager._initialized = True
    manager._max_queue_size = 10
    manager._max_concurrent = 1
    manager._semaphore = asyncio.Semaphore(1)
    manager._queued = 1

    await manager.acquire_slot()
    state_running = await manager.state()
    assert state_running["running"] == 1
    assert state_running["queued"] == 0

    await manager.release_slot()
    state_done = await manager.state()
    assert state_done["running"] == 0


def test_env_override_for_queue_size(monkeypatch, temp_concurrency_profile):
    monkeypatch.setenv("SKILL_RUNNER_MAX_QUEUE_SIZE", "3")
    manager = ConcurrencyManager()
    monkeypatch.setattr(manager, "_compute_max_concurrency", lambda policy: 4)
    manager.start()
    assert manager._max_queue_size == 3
    assert manager._max_concurrent == 4


def test_windows_limit_uses_minimum_of_all_dimensions(monkeypatch):
    manager = ConcurrencyManager()
    policy = {
        "fallback_max_concurrent": 2,
        "cpu_factor": 1.0,
        "mem_reserve_mb": 256,
        "estimated_mem_per_run_mb": 256,
        "fd_reserve": 64,
        "estimated_fd_per_run": 8,
        "pid_reserve": 16,
        "estimated_pid_per_run": 1,
        "max_concurrent_hard_cap": 16,
    }
    monkeypatch.setattr(manager, "_is_windows", lambda: True)
    monkeypatch.setattr(cm_module.os, "cpu_count", lambda: 8)
    monkeypatch.setattr(manager, "_mem_available_mb", lambda: 3000)
    monkeypatch.setattr(manager, "_windows_fd_limit", lambda _policy, _hard_cap: 6)
    monkeypatch.setattr(manager, "_windows_pid_limit", lambda _policy, _hard_cap: 12)
    assert manager._compute_max_concurrency(policy) == 6


def test_windows_pid_limit_not_constrained_without_job_limit(monkeypatch):
    manager = ConcurrencyManager()
    policy = {
        "pid_reserve": 16,
        "estimated_pid_per_run": 2,
    }
    monkeypatch.setattr(manager, "_windows_active_process_limit", lambda: None)
    assert manager._windows_pid_limit(policy, hard_cap=20) == 20


def test_windows_pid_limit_constrained_with_job_limit(monkeypatch):
    manager = ConcurrencyManager()
    policy = {
        "pid_reserve": 10,
        "estimated_pid_per_run": 3,
    }
    monkeypatch.setattr(manager, "_windows_active_process_limit", lambda: 40)
    assert manager._windows_pid_limit(policy, hard_cap=100) == 10


def test_windows_missing_psutil_fails_fast(monkeypatch):
    manager = ConcurrencyManager()
    policy = {
        "max_concurrent_hard_cap": 16,
        "max_queue_size": 8,
        "cpu_factor": 1.0,
        "mem_reserve_mb": 256,
        "estimated_mem_per_run_mb": 256,
        "fd_reserve": 64,
        "estimated_fd_per_run": 8,
        "pid_reserve": 16,
        "estimated_pid_per_run": 1,
        "fallback_max_concurrent": 2,
    }
    monkeypatch.setattr(cm_module, "psutil", None)
    monkeypatch.setattr(manager, "_is_windows", lambda: True)
    monkeypatch.setattr(manager, "_load_policy", lambda: policy)
    with pytest.raises(cm_module._WindowsConcurrencyProbeFatal, match="psutil"):
        manager.start()


def test_non_windows_probe_error_still_uses_fallback(monkeypatch):
    manager = ConcurrencyManager()
    policy = {
        "max_concurrent_hard_cap": 16,
        "max_queue_size": 8,
        "cpu_factor": 1.0,
        "mem_reserve_mb": 256,
        "estimated_mem_per_run_mb": 256,
        "fd_reserve": 64,
        "estimated_fd_per_run": 8,
        "pid_reserve": 16,
        "estimated_pid_per_run": 1,
        "fallback_max_concurrent": 2,
    }
    monkeypatch.setattr(manager, "_is_windows", lambda: False)
    monkeypatch.setattr(cm_module.os, "cpu_count", lambda: 8)
    monkeypatch.setattr(manager, "_mem_available_mb", lambda: (_ for _ in ()).throw(RuntimeError("probe fail")))
    assert manager._compute_max_concurrency(policy) == 2
