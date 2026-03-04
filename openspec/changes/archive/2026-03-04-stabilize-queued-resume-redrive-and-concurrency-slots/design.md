# Design: stabilize-queued-resume-redrive-and-concurrency-slots

## Context

Interactive reply/auth resumes currently depend on a queued redrive path:

1. reply or auth completion issues a resume ticket and moves the run to `queued`
2. the resumed attempt eventually re-enters `run_job()`
3. observability and recovery can redrive queued resumes when they believe the run is still resumable

The failure cluster comes from two boundary mistakes:

- lifecycle admission is not guaranteed to release its slot on every post-acquire exit path
- queued redrive policy does not distinguish runnable queued runs from orphan queued runs with missing runtime assets

## Goals

- release concurrency slots exactly once on every post-acquire lifecycle exit
- prevent queued redrive when the run directory is gone
- reconcile orphan queued runs to a deterministic terminal failure
- keep observability as a trigger only, not a policy owner

## Non-Goals

- no queue policy redesign
- no new HTTP API
- no new FCMP event types
- no resume ticket ownership redesign beyond this failure mode

## Decisions

### 1. Slot safety is guaranteed by lifecycle finalization

Once `run_job()` acquires a slot, every subsequent return path MUST pass through one outer `finally` block that releases the slot exactly once.

Implementation rule:

- keep `slot_acquired=False`
- set it to `True` immediately after a successful acquire
- remove ad hoc early-return release branches
- let the outermost `finally` own slot release

### 2. Missing `run_dir` is a canonical non-runnable orphan condition

A queued resume is only redrivable if its run directory still exists.

If the run directory is missing:

- the run is no longer runnable
- recovery MUST NOT schedule a resumed attempt
- observability MUST NOT try to compensate locally

### 3. Orphan queued runs reconcile to `failed`

When queued redrive discovers that `run_dir` is missing, the system MUST reconcile the run to:

- `status=failed`
- `recovery_state=failed_reconciled`
- `recovery_reason=missing_run_dir_before_resume_redrive`

Cleanup on this path:

- clear pending interaction
- clear pending auth
- clear pending auth method selection
- clear engine session handle
- clear auth resume context

The preferred failure class remains the existing recovery/session-resume family; no new public error family is introduced.

### 4. Observability stays thin

`run_observability.py` may still trigger queued redrive, but it does not decide whether a run is orphaned.

Policy ownership stays in `RunRecoveryService`:

- determine whether queued resume is redrivable
- reconcile orphan queued runs
- persist failed reconciliation metadata

Observability only refreshes its view after recovery has acted.

## Execution Flow

### Normal queued resume

1. reply/auth completion issues a resume ticket
2. run enters `queued`
3. recovery verifies `run_dir` exists
4. resumed attempt is scheduled
5. lifecycle marks resume ticket started and continues normally

### Orphan queued resume

1. reply/auth completion leaves the run at `queued`
2. recovery checks queued redrive preconditions
3. `run_dir` is missing
4. recovery marks the run `failed_reconciled`
5. no target attempt is materialized

## Files To Change

- `server/services/orchestration/run_job_lifecycle_service.py`
- `server/services/orchestration/run_recovery_service.py`
- `server/runtime/observability/run_observability.py`
- runtime SSOT/docs/specs
- regression tests for lifecycle, recovery, and observability
