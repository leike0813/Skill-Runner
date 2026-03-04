# Tasks: stabilize-runtime-resume-idempotency-and-attempt-ownership

- [x] Add a new OpenSpec delta change for runtime resume idempotency and attempt ownership
- [x] Update interactive lifecycle, runtime event schema, and interactive job API delta specs for resume ownership semantics
- [x] Extend runtime SSOT contract and docs with resume ticket, pending owner, and attempt-scoped invariants
- [x] Add durable resume ticket persistence to the run store
- [x] Refactor auth, interaction reply, and recovery paths to share a single-consumer resume ticket flow
- [x] Materialize target attempts before `turn.started` and prevent duplicate started events for the same resume
- [x] Make pending/history/result attempt-scoped in observability and terminal result rendering
- [x] Update frontend observer reads so waiting views use current pending and terminal views use terminal result only
- [x] Add or update tests for resume ticket idempotency, protocol payloads, observability, and restart recovery
- [x] Run targeted pytest suites and mypy for changed modules
- [x] Introduce current projection as the single source of truth for current run state
- [x] Make `result/result.json` terminal-only and move waiting/current reads to projection + pending owner
- [x] Update observability, status APIs, and frontend readers to prefer current projection over stale result payloads
