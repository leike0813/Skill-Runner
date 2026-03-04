from server.runtime.protocol.ordering_gate import (
    OrderingPrerequisite,
    RuntimeEventCandidate,
    RuntimeEventOrderingGate,
)


def test_ordering_gate_buffers_until_prerequisite_publish_id_is_seen() -> None:
    gate = RuntimeEventOrderingGate()
    blocked = RuntimeEventCandidate(
        stream="fcmp",
        source_kind="orchestration",
        event_kind="projection.terminal.result",
        run_id="run-1",
        attempt_number=1,
        publish_id="p-blocked",
        prerequisites=[OrderingPrerequisite(event_kind="conversation.state.changed.succeeded", publish_id="p-terminal")],
    )
    decision = gate.decide(blocked)
    assert decision.kind == "buffer"

    terminal = RuntimeEventCandidate(
        stream="fcmp",
        source_kind="orchestration",
        event_kind="conversation.state.changed.succeeded",
        run_id="run-1",
        attempt_number=1,
        publish_id="p-terminal",
    )
    terminal_decision = gate.decide(terminal)
    assert terminal_decision.kind == "publish"

    released = gate.release_ready()
    assert [candidate.publish_id for candidate in released] == ["p-blocked"]


def test_ordering_gate_publishes_ready_candidate_immediately() -> None:
    gate = RuntimeEventOrderingGate()
    candidate = RuntimeEventCandidate(
        stream="rasp",
        source_kind="parser",
        event_kind="assistant.message.final",
        run_id="run-2",
        attempt_number=1,
        publish_id="p-ready",
    )
    decision = gate.decide(candidate)
    assert decision.kind == "publish"
    assert gate.release_ready() == []
