import pytest

from server.services.engine_interaction_gate import EngineInteractionBusyError, EngineInteractionGate


def test_engine_interaction_gate_allows_single_active_session():
    gate = EngineInteractionGate()
    acquired = gate.acquire("ui_tui", session_id="s-1", engine="codex")
    assert acquired["scope"] == "ui_tui"
    assert gate.snapshot()["active"] is True

    gate.release("ui_tui", "s-1")
    assert gate.snapshot()["active"] is False


def test_engine_interaction_gate_rejects_conflicting_scope():
    gate = EngineInteractionGate()
    gate.acquire("auth_flow", session_id="a-1", engine="codex")
    with pytest.raises(EngineInteractionBusyError):
        gate.acquire("ui_tui", session_id="t-1", engine="codex")
