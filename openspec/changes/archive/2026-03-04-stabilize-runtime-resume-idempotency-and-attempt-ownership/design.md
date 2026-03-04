# Design: stabilize-runtime-resume-idempotency-and-attempt-ownership

## Summary

Keep the canonical top-level statechart unchanged, but add a durable resume ownership layer:

- `waiting_user` and `waiting_auth` each have one current pending owner
- leaving a waiting state requires a durable resume ticket
- the winner that consumes the ticket is the only path allowed to create the next attempt
- `queued -> running` is the point where the target attempt is materialized
- `current projection` is the only current-state truth; terminal result is a separate artifact

## Core Decisions

### 0. Execution mode and client conversation capability are orthogonal

This change treats runtime behavior as a matrix of:

- `execution_mode`: `auto` or `interactive`
- `client_metadata.conversation_mode`: `session` or `non_session`

Rules:

- `waiting_auth` requires `conversation_mode=session`, but may occur in both `auto` and `interactive`
- real `waiting_user` requires `execution_mode=interactive` and `conversation_mode=session`
- `non_session` clients never enter `waiting_auth`
- `non_session` clients never enter real `waiting_user`
- if a `non_session` client executes an interactive-only skill, the backend normalizes it to pseudo-interactive with `interactive_auto_reply=true` and `interactive_reply_timeout_sec=0`

### 1. No new top-level runtime state

This change does not add a new canonical top-level state.

- `queued`
- `running`
- `waiting_user`
- `waiting_auth`
- `succeeded`
- `failed`
- `canceled`

`method_selection` remains an internal `waiting_auth` phase/read model.

### 2. Resume ownership is durable and single-consumer

All waiting-state resume paths share one persisted ticket contract:

- callback completion
- `/auth/session` reconcile
- restart recovery
- user reply acceptance
- auto-decision timeout

Ticket states:

- `issued`
- `dispatched`
- `started`

Only the path that transitions the ticket forward is allowed to advance the run.

### 3. Attempt materialization happens before `turn.started`

Resume processing must determine:

- `source_attempt`
- `target_attempt`
- `resume_cause`
- `resume_ticket_id`

before any `lifecycle.run.started` / `turn.started` side effects are emitted.

`auth.session.completed.resume_attempt` is treated as the target attempt, not the attempt that emitted the completion event.

### 4. Current projection, current pending, history, and terminal result are different truth layers

Persisted run truth is split into four layers:

- current projection
- current pending read model
- append-only history
- terminal result

Rules:

- `current/projection.json` and durable projection storage are the single source of truth for current run state
- `pending.json` / `pending_auth*.json` represent only the current waiting owner
- `history.jsonl` and interaction history entries carry `source_attempt`
- non-terminal states must not be written into `result/result.json`
- terminal `result/result.json` must only exist for `succeeded|failed|canceled` terminal truth
- frontend terminal summary reads only terminal result, never stale pending/history

### 5. `interaction_id` remains integer but becomes attempt-scoped

This change does not introduce a global interaction UUID.

Instead:

- `interaction_id` remains an integer
- its identity is scoped to the attempt that produced it
- observability and reconciliation must use `source_attempt + interaction_id`, not `interaction_id` alone

## Data Model

### Resume Ticket

Persisted fields:

- `ticket_id`
- `cause`
- `source_attempt`
- `target_attempt`
- `state`
- `created_at`
- `updated_at`
- `dispatched_at`
- `started_at`
- `payload`

### Pending Owner

Canonical read-model owner values:

- `waiting_user`
- `waiting_auth.method_selection`
- `waiting_auth.challenge_active`

### Current Projection

Persisted fields:

- `status`
- `updated_at`
- `current_attempt`
- `pending_owner`
- `pending_interaction_id`
- `pending_auth_session_id`
- `resume_ticket_id`
- `resume_cause`
- `source_attempt`
- `target_attempt`
- `conversation_mode`
- `requested_execution_mode`
- `effective_execution_mode`
- `effective_interactive_require_user_reply`
- `effective_interactive_reply_timeout_sec`
- `effective_session_timeout_sec`
- `error`
- `warnings`

### Protocol Extensions

Optional protocol fields:

- `resume_cause`
- `pending_owner`
- `source_attempt`
- `target_attempt`
- `resume_ticket_id`
- `ticket_consumed`

## Integration Points

### Run Store

The run store becomes the durable owner of:

- current projection persistence
- resume ticket issuance
- winner selection through state transition
- attempt-scoped pending/history persistence

### Orchestration

`run_auth_orchestration_service`, `run_interaction_service`, and `run_recovery_service` all use the same ticket path.

### Observability

FCMP materialization must derive waiting and resume semantics from:

- canonical current projection
- current pending owner
- attempt-scoped audit/history entries

### Frontend

The web observer remains a thin client:

- waiting UI reads current pending only
- terminal summary reads terminal result only
- pollers may trigger refresh, but may not infer resume state locally
