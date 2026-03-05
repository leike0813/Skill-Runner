import asyncio

import pytest

from server.config import config
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
