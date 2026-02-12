## Context

Skill-Runner creates an isolated `run_dir` per execution, then invokes Codex/Gemini/iFlow adapters.
Today, no explicit trust lifecycle is applied to these `run_dir` paths in global CLI configs.
For Codex and Gemini this can produce unstable behavior in sandboxed or guarded environments, especially when per-run directories are new each time.

Current constraints:
- Codex trust is managed in `~/.codex/config.toml` via `projects."<path>".trust_level`.
- Gemini trust is managed in `~/.gemini/trustedFolders.json` as a JSON object of `path -> TRUST_FOLDER`.
- iFlow currently has no stable trust-folder mechanism we can rely on.
- Global config files are shared across runs, so stale entries can grow without cleanup.

Stakeholders:
- API users expecting deterministic non-interactive runs.
- Operators running containerized deployments with shared global config mounts.

## Goals / Non-Goals

**Goals:**
- Add a deterministic trust lifecycle for Codex/Gemini run directories:
  - register trust before CLI execution
  - remove trust after execution
- Keep trust records bounded and avoid unbounded config growth.
- Bootstrap trust configuration safely at container startup for the run root parent directory.
- Preserve current iFlow behavior without regressions.

**Non-Goals:**
- Introducing iFlow trust semantics without official stable support.
- Migrating trust storage away from each CLI's native config files.
- Refactoring adapter architecture beyond the minimum hooks needed for trust lifecycle.

## Decisions

### Decision 1: Introduce a dedicated trust manager service
Create `RunFolderTrustManager` (new service) to centralize all trust operations.

Why:
- Avoid duplicating file-format and locking logic in adapters.
- Keep Codex/Gemini format-specific code isolated and testable.

Alternatives considered:
- Implement trust writes directly in each adapter.
  - Rejected: duplicates logic and increases drift risk.

### Decision 2: Apply trust lifecycle around adapter execution
In orchestration flow:
1. Resolve `run_dir`
2. Register trust for active engine (Codex/Gemini)
3. Execute adapter
4. Remove trust in `finally`

Why:
- Ensures cleanup executes for both success and failure paths.
- Keeps lifecycle aligned with actual execution window.

Alternatives considered:
- Register once at run creation time and cleanup via periodic GC.
  - Rejected: broader trust window and more stale records.

### Decision 3: Container bootstrap creates missing trust config files and parent trust entry
`entrypoint.sh` will:
- ensure `~/.gemini/trustedFolders.json` exists as `{}` when missing or invalid
- add run parent directory trust (`/data/runs` by default) for Gemini
- add Codex `projects."<runs_parent>".trust_level = "trusted"`

Why:
- Reduces first-run friction in fresh containers.
- Keeps behavior deterministic even before first job.

Alternatives considered:
- Only runtime per-run writes with no bootstrap.
  - Rejected: increases cold-start instability and first-run edge cases.

### Decision 4: Concurrency-safe config updates with best-effort cleanup
Trust manager updates global config files atomically (read-modify-write with file lock).
Cleanup failures are logged and retried via periodic cleanup scan.

Why:
- Multiple concurrent jobs may update shared config files.
- Cleanup should not mask real job outcomes.

Alternatives considered:
- Ignore concurrency and rely on low contention.
  - Rejected: high risk of corrupted/truncated config state.

## Risks / Trade-offs

- [Risk] Global config mutation race across parallel runs -> Mitigation: file locking + atomic replace writes.
- [Risk] Cleanup misses on process crash -> Mitigation: periodic trust GC scanning active runs and removing stale entries.
- [Risk] Path canonicalization mismatch (symlink/relative paths) -> Mitigation: always normalize to absolute resolved path before read/write.
- [Risk] Windows path escaping differences for Gemini JSON keys -> Mitigation: use native path serialization from `Path.resolve()` and JSON encoder.
- [Risk] Entry-point bootstrap may overwrite malformed user files -> Mitigation: preserve backup copy before repairing invalid JSON/TOML.

## Migration Plan

1. Add trust manager service and unit tests for Codex/Gemini file mutations.
2. Hook orchestrator execution flow with `register -> execute -> cleanup`.
3. Add startup bootstrap in `scripts/entrypoint.sh`.
4. Add periodic stale-trust cleanup job (best effort).
5. Update docs (`containerization.md`, `execution_flow.md`, `adapter_design.md`).
6. Rollback strategy:
   - disable trust calls in orchestrator (feature gate via env if needed)
   - retain existing adapter execution path unchanged.

## Open Questions

- Should trust cleanup use the existing run cleanup scheduler or a dedicated scheduler job?
- Should parent directory bootstrap be configurable via env (e.g. `SKILL_RUNNER_TRUST_ROOT`) beyond `SKILL_RUNNER_DATA_DIR`?
- Do we want to persist trust-manager operation audit logs in `run_dir/logs` in addition to server logs?
