## Context

Skill Runner currently executes jobs only against skills pre-registered under `skills/` and discovered by `SkillRegistry`. We now need a parallel workflow for one-off execution: clients upload a temporary skill package, run it, and discard it after use.

Constraints:
- Temporary skill packages must use the same AutoSkill Profile validation baseline as persistent skills.
- Temporary skills must not mutate persistent `skills/` registry state.
- Execution must still pass through existing job lifecycle guarantees (status, logs, result validation, artifacts handling).
- The API must be two-step because both temporary skill package and run input files need upload support.

## Goals / Non-Goals

**Goals:**
- Add API support for uploading a temporary skill package and submitting a run.
- Validate temporary skill package structure and metadata before run creation.
- Execute with isolation equivalent to regular runs.
- Ensure temporary skill files are cleaned after run terminal states.

**Non-Goals:**
- Persist temporary skills in `skills/`.
- Add version upgrade/archive semantics for temporary skills.
- Introduce a marketplace/registry mechanism for temporary skills.

## Decisions

### Decision 1: Two-step temporary API under `/v1/temp-skill-runs`
Introduce dedicated two-step endpoints for temporary skill flow:
- Step 1: create temporary run request
- Step 2: upload temporary skill package and input files, then start execution

Why:
- Keeps existing stable job API contract intact.
- Matches requirement to upload both skill package and run input files.
- Avoids ambiguous precedence between `skill_id` and uploaded package.

Alternative considered:
- Extending `/v1/jobs` with optional temporary package fields. Rejected due to mixed concerns and backward-compatibility risk.

### Decision 2: Stage temporary skills under request-scoped storage
Store each temporary package and extracted skill under request-scoped directories in data space (not under `skills/`).

Why:
- Prevents accidental pollution of persistent registry.
- Enables deterministic cleanup by request/run linkage.

Alternative considered:
- Reuse `skills/.staging`. Rejected because this area is tied to persistent install/update workflow and archive semantics.

### Decision 3: Reuse AutoSkill validation logic
Factor validation into reusable checks, then apply them both for persistent install and temporary upload.

Why:
- Single source of truth for skill validity.
- Reduces drift between install and temporary execution behavior.

Alternative considered:
- Implement temporary-specific lightweight validation. Rejected due to inconsistency risk.

### Decision 4: Bind temporary skill to run at orchestration time
Resolve the temporary skill path during request-to-run transition, then pass that path into job orchestration/adapter setup instead of global registry lookup.

Why:
- Keeps execution deterministic even if another temporary request uploads similarly named skills.
- Enables straightforward cleanup once run reaches terminal status.

Alternative considered:
- Register temporary skill into `SkillRegistry` with synthetic ids. Rejected due to cache/discovery side effects.

### Decision 5: No cache for temporary skills
Temporary skill runs never participate in cache lookup or cache write-back.

Why:
- Temporary package content is request-scoped and short-lived.
- Avoids cache-key complexity based on transient package state.

Alternative considered:
- Cache by package hash. Rejected in v1 to keep behavior deterministic and simple.

### Decision 6: Cleanup on terminal status with fallback janitor
Primary cleanup occurs immediately after run completion (succeeded/failed/canceled). Add dedicated periodic cleanup task for orphaned temporary directories as defense in depth.

Why:
- Immediate release of disk space.
- Handles crash/interruption scenarios.

Alternative considered:
- TTL-only cleanup. Rejected because unnecessary delay keeps stale files around.

### Decision 7: Cleanup failure handling is warning-only
If immediate cleanup fails, the system records warning logs and relies on periodic cleanup. No in-request retry cascade.

Why:
- Keeps terminal-state path bounded and predictable.
- Avoids long-tail latency at request completion.

Alternative considered:
- Immediate multi-retry logic. Rejected due to complexity and limited practical gain.

### Decision 8: Size limits and zip path safety are mandatory
Temporary package upload enforces package size limit and extraction safety checks (zip slip prevention, unsafe path rejection).

Why:
- Prevents resource abuse and path traversal vulnerabilities.
- Aligns temporary flow with production-safe upload posture.

## Risks / Trade-offs

- [Risk] Validation reuse refactor may impact existing install flow. → Mitigation: add unit tests around shared validator and run existing install tests.
- [Risk] Cleanup race with artifact retrieval/log queries. → Mitigation: keep run outputs in run_dir; only delete temporary skill staging/content.
- [Risk] More request states and code paths increase complexity. → Mitigation: isolate temporary-skill manager/service and keep router contracts explicit.
- [Risk] Two-step API increases client integration complexity. → Mitigation: align request/status/error semantics with existing jobs API to minimize cognitive overhead.

## Migration Plan

1. Add temporary-skill request models and router endpoints under `/v1/temp-skill-runs`.
2. Introduce temporary skill manager with validate + stage + cleanup primitives.
3. Add orchestration branch for temporary skill execution without touching registry-based path.
4. Add periodic temporary-skill orphan cleanup task.
5. Add tests (unit + integration) for temporary upload/run/cleanup and failure paths.
5. Update API and test documentation.

Rollback:
- Remove router registration for temporary-skill endpoints.
- Existing persistent skill execution remains unchanged.

## Open Questions

- Exact numeric defaults for package max size and extracted total size.
- Whether to expose cleanup warnings in status API or keep them in logs only.
