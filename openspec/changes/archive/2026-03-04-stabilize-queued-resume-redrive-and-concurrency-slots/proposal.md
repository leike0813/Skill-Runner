# Proposal: stabilize-queued-resume-redrive-and-concurrency-slots

## Why

Recent interactive resume runs exposed a new failure cluster:

- `run_job()` can acquire a concurrency slot and then return early when `run_dir` is missing
- those early exits can leak slots and slowly saturate the global semaphore
- orphan queued runs with stale resume tickets can be redriven repeatedly by observability/recovery
- legitimate resumed attempts then stall in `queued` because they cannot acquire a slot

This is not a resume-ticket ownership bug. It is a runtime admission and orphan-recovery bug.

The current system also conflates two different queued states:

- runnable queued work that can legitimately redrive
- irrecoverable orphan queued work whose runtime assets are already gone

That ambiguity causes repeated `Run dir <id> not found` storms, resume tickets stuck in `dispatched`, and misleading empty attempt-audit placeholders even though no new attempt actually started.

## What Changes

This change:

1. guarantees concurrency slot release on every `run_job()` exit after acquisition
2. makes queued resume redrive conditional on the run directory still existing
3. reconciles orphan queued runs with missing run directories to terminal `failed`
4. keeps observability as a thin trigger and moves orphan-vs-runnable policy into recovery services
5. updates runtime SSOT/docs/specs so `queued` no longer implies “always safe to redrive”

## Impact

- affects runtime lifecycle execution, queued resume recovery, and observability-triggered redrive
- keeps external HTTP APIs and FCMP event shapes unchanged
- reduces log storms from orphan queued runs
- prevents unrelated orphan runs from blocking healthy interactive replies/auth resumes
