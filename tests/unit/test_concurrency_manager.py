import asyncio
import json
from pathlib import Path

import pytest

from server.config import config
from server.services.platform.concurrency_manager import ConcurrencyManager


@pytest.fixture
def temp_concurrency_policy(tmp_path):
    policy_path = tmp_path / "concurrency_policy.json"
    policy_path.write_text(
        json.dumps(
            {
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
        ),
        encoding="utf-8",
    )
    old_policy = config.SYSTEM.CONCURRENCY_POLICY
    config.defrost()
    config.SYSTEM.CONCURRENCY_POLICY = str(policy_path)
    config.freeze()
    try:
        yield policy_path
    finally:
        config.defrost()
        config.SYSTEM.CONCURRENCY_POLICY = old_policy
        config.freeze()


def test_start_fallback_when_policy_missing(monkeypatch):
    manager = ConcurrencyManager()
    old_policy = config.SYSTEM.CONCURRENCY_POLICY
    config.defrost()
    config.SYSTEM.CONCURRENCY_POLICY = "/tmp/does-not-exist-concurrency-policy.json"
    config.freeze()
    try:
        manager.start()
        assert manager._max_concurrent == 2
        assert manager._max_queue_size == 128
    finally:
        config.defrost()
        config.SYSTEM.CONCURRENCY_POLICY = old_policy
        config.freeze()


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


def test_env_override_for_queue_size(monkeypatch, temp_concurrency_policy):
    monkeypatch.setenv("SKILL_RUNNER_MAX_QUEUE_SIZE", "3")
    manager = ConcurrencyManager()
    monkeypatch.setattr(manager, "_compute_max_concurrency", lambda policy: 4)
    manager.start()
    assert manager._max_queue_size == 3
    assert manager._max_concurrent == 4
