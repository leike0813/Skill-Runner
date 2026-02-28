from __future__ import annotations

from pathlib import Path


def test_runtime_execution_business_modules_are_relocated() -> None:
    assert not Path("server/runtime/execution/run_execution_core.py").exists()
    assert not Path("server/runtime/execution/run_interaction_service.py").exists()
    assert Path("server/services/orchestration/run_execution_core.py").exists()
    assert Path("server/services/orchestration/run_interaction_service.py").exists()
