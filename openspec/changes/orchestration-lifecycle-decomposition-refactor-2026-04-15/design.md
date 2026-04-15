## Design Summary

The refactor is intentionally staged. Each stage extracts one orchestration responsibility behind a dedicated service and keeps `JobOrchestrator` as the stable façade that upstream callers continue to use.

The first implementation slice in this change lands:

1. façade guardrails for `JobOrchestrator`
2. a dedicated `RunAttemptPreparationService`
3. a typed `RunAttemptContext`

Later stages will extract execution, outcome normalization, projection finalization, and audit finalization behind similarly explicit boundaries.

## Key Decisions

### Stage-by-stage decomposition

This change does not attempt a one-shot rewrite of `run_job`. Instead it codifies a staged decomposition path:

- Stage 0: guardrail tests + change scaffolding
- Stage 1: extract run-attempt preparation
- Stage 2: extract adapter execution
- Stage 3: extract outcome normalization
- Stage 4: extract projection/audit finalizers
- Stage 5: slim `JobOrchestrator` and split the giant orchestrator test file

Each stage is only allowed to proceed after its targeted tests are green.

### Preparation is the first slice

Run-attempt preparation is the safest first extraction because it naturally groups:

- request/request record lookup
- execution-mode and attempt-number resolution
- skill/adapter/input validation
- run-option construction and resume-context injection
- pre-execution schema materialization

This stage stops before adapter execution and before any waiting/auth/final outcome classification.

### Explicit typed handoff

`RunAttemptPreparationService` returns a `RunAttemptContext` dataclass rather than a loose dict. That context becomes the canonical handoff from preparation to the remaining lifecycle pipeline.

The context includes only preparation outputs that later stages need, such as:

- run/request metadata
- interactive/session gating flags
- selected skill and adapter
- validated `input_data`
- materialized `run_options`
- preparation-time custom-provider model resolution

### Stable façade first

`JobOrchestrator.run_job`, `cancel_run`, and `recover_incomplete_runs_on_startup` remain the public orchestration entrypoints throughout the refactor. The new services are internal implementation boundaries, not new public APIs.
