from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal


StreamName = Literal["fcmp", "rasp"]
SourceKind = Literal["parser", "orchestration", "projection"]
DecisionKind = Literal["publish", "buffer"]


@dataclass(frozen=True)
class OrderingPrerequisite:
    event_kind: str
    publish_id: str | None = None


@dataclass(frozen=True)
class RuntimeEventCandidate:
    stream: StreamName
    source_kind: SourceKind
    event_kind: str
    run_id: str
    attempt_number: int
    publish_id: str
    caused_by_publish_id: str | None = None
    payload: Dict[str, Any] = field(default_factory=dict)
    prerequisites: List[OrderingPrerequisite] = field(default_factory=list)


@dataclass(frozen=True)
class OrderingDecision:
    kind: DecisionKind
    candidate: RuntimeEventCandidate
    reason: str


@dataclass
class ProjectionGateState:
    terminal_publish_id: str | None = None
    terminal_status: str | None = None


class _BaseOrderingBuffer:
    def __init__(self) -> None:
        self._items: List[RuntimeEventCandidate] = []

    def push(self, candidate: RuntimeEventCandidate) -> None:
        self._items.append(candidate)

    def release_ready(self, published_ids: set[str]) -> List[RuntimeEventCandidate]:
        ready: List[RuntimeEventCandidate] = []
        pending: List[RuntimeEventCandidate] = []
        for candidate in self._items:
            if all(
                prereq.publish_id in published_ids or prereq.publish_id is None
                for prereq in candidate.prerequisites
            ):
                ready.append(candidate)
            else:
                pending.append(candidate)
        self._items = pending
        return ready


class FcmpOrderingBuffer(_BaseOrderingBuffer):
    pass


class RaspOrderingBuffer(_BaseOrderingBuffer):
    pass


class RuntimeEventOrderingGate:
    def __init__(self) -> None:
        self._published_ids: set[str] = set()
        self._published_event_kinds: set[str] = set()
        self._fcmp_buffer = FcmpOrderingBuffer()
        self._rasp_buffer = RaspOrderingBuffer()

    def _prerequisite_satisfied(self, prerequisite: OrderingPrerequisite) -> bool:
        if prerequisite.publish_id is not None:
            return prerequisite.publish_id in self._published_ids
        return prerequisite.event_kind in self._published_event_kinds

    def _mark_published(self, candidate: RuntimeEventCandidate) -> None:
        self._published_ids.add(candidate.publish_id)
        self._published_event_kinds.add(candidate.event_kind)

    def decide(self, candidate: RuntimeEventCandidate) -> OrderingDecision:
        if all(
            self._prerequisite_satisfied(prereq)
            for prereq in candidate.prerequisites
        ):
            self._mark_published(candidate)
            return OrderingDecision(kind="publish", candidate=candidate, reason="prerequisites_satisfied")
        buffer = self._fcmp_buffer if candidate.stream == "fcmp" else self._rasp_buffer
        buffer.push(candidate)
        return OrderingDecision(kind="buffer", candidate=candidate, reason="prerequisites_not_satisfied")

    def release_ready(self) -> List[RuntimeEventCandidate]:
        released: List[RuntimeEventCandidate] = []
        while True:
            newly_released: List[RuntimeEventCandidate] = []
            for buffer in (self._fcmp_buffer, self._rasp_buffer):
                ready = buffer.release_ready(self._published_ids)
                for candidate in ready:
                    if all(self._prerequisite_satisfied(prereq) for prereq in candidate.prerequisites):
                        self._mark_published(candidate)
                        newly_released.append(candidate)
                    else:
                        buffer.push(candidate)
            if not newly_released:
                break
            released.extend(newly_released)
        return released
