from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Iterable

from server.models import RunStatus


class SessionEvent:
    TURN_STARTED = "turn.started"
    TURN_NEEDS_INPUT = "turn.needs_input"
    USER_REPLY_ACCEPTED = "interaction.reply.accepted"
    AUTO_DECIDE_TIMEOUT = "interaction.auto_decide.timeout"
    TURN_SUCCEEDED = "turn.succeeded"
    TURN_FAILED = "turn.failed"
    CANCELED = "run.canceled"
    RESTART_PRESERVE_WAITING = "restart.preserve_waiting"
    RESTART_RECONCILE_FAILED = "restart.reconcile_failed"


TERMINAL_STATES = {
    RunStatus.SUCCEEDED.value,
    RunStatus.FAILED.value,
    RunStatus.CANCELED.value,
}


@dataclass(frozen=True)
class Transition:
    source: str
    event: str
    target: str
    guard: str = "always"
    action: str = "none"


TRANSITIONS: tuple[Transition, ...] = (
    Transition("queued", SessionEvent.TURN_STARTED, "running", action="acquire_slot"),
    Transition("running", SessionEvent.TURN_NEEDS_INPUT, "waiting_user", action="persist_pending"),
    Transition("waiting_user", SessionEvent.USER_REPLY_ACCEPTED, "queued", action="requeue_resume_turn"),
    Transition("waiting_user", SessionEvent.AUTO_DECIDE_TIMEOUT, "queued", action="requeue_auto_resume_turn"),
    Transition("running", SessionEvent.TURN_SUCCEEDED, "succeeded"),
    Transition("running", SessionEvent.TURN_FAILED, "failed"),
    Transition("waiting_user", SessionEvent.CANCELED, "canceled"),
    Transition("queued", SessionEvent.CANCELED, "canceled"),
    Transition("running", SessionEvent.CANCELED, "canceled"),
    Transition("waiting_user", SessionEvent.RESTART_PRESERVE_WAITING, "waiting_user"),
    Transition("waiting_user", SessionEvent.RESTART_RECONCILE_FAILED, "failed"),
    Transition("queued", SessionEvent.RESTART_RECONCILE_FAILED, "failed"),
    Transition("running", SessionEvent.RESTART_RECONCILE_FAILED, "failed"),
)


def transition_rows() -> Iterable[Transition]:
    return TRANSITIONS


def timeout_requires_auto_decision(interactive_auto_reply: bool) -> bool:
    return interactive_auto_reply


def waiting_reply_target_status() -> RunStatus:
    return RunStatus.QUEUED


def waiting_recovery_event(*, has_pending_interaction: bool, has_valid_handle: bool) -> str:
    if has_pending_interaction and has_valid_handle:
        return SessionEvent.RESTART_PRESERVE_WAITING
    return SessionEvent.RESTART_RECONCILE_FAILED


def assert_terminal_status_exclusive(status: RunStatus) -> bool:
    return status.value in TERMINAL_STATES


def build_transition_index() -> Dict[tuple[str, str], Transition]:
    return {(row.source, row.event): row for row in TRANSITIONS}
