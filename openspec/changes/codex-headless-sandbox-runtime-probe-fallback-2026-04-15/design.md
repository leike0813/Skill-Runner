## Context

Codex headless runs operate through two separate but coupled control surfaces:

1. command construction (`--full-auto` vs `--yolo`)
2. generated Codex profile (`sandbox_mode`, `approval_policy`, and related settings)

The bug was that only the first surface had any downgrade logic, and even that logic depended only
on `LANDLOCK_ENABLED=0`. In environments where `bwrap` existed but failed to initialize at runtime,
the command and generated config diverged from the real capability of the host. That mismatch caused
headless runs to continue requesting `workspace-write` sandboxing even though the sandbox runtime
could not start.

Claude already used a persisted sandbox probe sidecar to gate headless sandbox config. This change
brings Codex to the same governance level, but keeps Codex-specific semantics: on probe failure,
headless Codex must degrade to a non-sandboxed auto mode that is actually executable.

## Goals / Non-Goals

**Goals:**

- Detect whether Codex sandboxing is really usable, not merely declared.
- Persist that result in a stable sidecar so command builders, config composers, and status APIs
  consume the same truth.
- Ensure fallback is effective:
  - command flags downgrade from `--full-auto` to `--yolo`
  - generated Codex profile downgrades from `workspace-write` to `danger-full-access`
- Keep static repository defaults unchanged and apply fallback only at runtime.

**Non-Goals:**

- Changing Codex UI shell launch policy.
- Changing public API schemas or event types.
- Reworking Codex trust lifecycle, structured-output governance, or auth handling.
- Introducing a new runtime override API surface beyond the existing internal composition path.

## Decisions

### 1. Codex sandbox availability is determined by a persisted runtime probe

Codex headless execution now uses a Codex-specific sandbox probe result, written to
`agent_home/.codex/sandbox_probe.json`.

The probe evaluates:

- explicit disable via `LANDLOCK_ENABLED=0`
- `bwrap` / `bubblewrap` dependency presence
- a minimal `bubblewrap` smoke test

If the smoke test fails with uid-map / permission-denied style initialization failures, the probe
is `available=false` even though the binary exists.

Rationale:

- The runtime must model actual executability, not just installation state.
- A persisted sidecar allows command, config, and management status code paths to reuse the same
  result instead of recomputing ad hoc heuristics.

### 2. Probe unavailability triggers a dual fallback, not a CLI-only fallback

When the probe is unavailable, headless Codex must degrade both:

- command flags: `--full-auto` -> `--yolo`
- generated config: `sandbox_mode = "danger-full-access"`

`approval_policy = "never"` remains unchanged.

Rationale:

- CLI-only downgrade is ineffective if the generated profile still requests `workspace-write`.
- The goal is not “best effort appearance of fallback”, but a headless launch path that avoids the
  failing sandbox runtime entirely.

Alternative considered:

- Leave `sandbox_mode` untouched and only adjust argv. Rejected because it preserves the failing
  bubblewrap path and does not solve the observed issue.

### 3. Runtime fallback is dynamic and must not rewrite static enforced policy

The repository default in `server/engines/codex/config/enforced.toml` remains the declared default.
The fallback applies only while composing the run-local / agent-home profile for a specific headless
launch.

Rationale:

- Static defaults should continue to express the intended secure baseline.
- Runtime unavailability is environment-dependent and must be represented as a launch-time gating
  decision, not a source-controlled policy rewrite.

### 4. Missing or unreadable sidecar must not fail open

If the Codex sandbox sidecar is missing or unreadable, headless paths must synchronously re-probe
and persist the result before deciding command flags or config.

Rationale:

- A missing cache entry is not evidence that sandboxing is available.
- This prevents headless execution from silently falling back to optimistic assumptions after cache
  loss or corruption.

### 5. Management status may reuse the same probe truth, but UI shell policy remains separate

`collect_sandbox_status("codex")` now surfaces the real probe result so management and diagnostics
can expose dependency-missing / runtime-unavailable messages consistently. This change does not
alter the existing Codex UI shell launch policy; it only upgrades the status source of truth.

Rationale:

- Reusing the same probe improves observability and avoids status drift.
- UI launch semantics are intentionally outside the scope of this slice.

## Risks / Trade-offs

- [Probe latency on cold cache] -> Accepted because the smoke test is short and only runs when the
  sidecar is missing or explicitly refreshed.
- [Static enforced config still says `workspace-write`] -> Accepted because the dynamic fallback is
  intentional and environment-specific, while the repo default remains the desired secure baseline.
- [Codex package import graph becomes more sensitive] -> Mitigated by keeping the probe module
  lightweight and avoiding eager adapter imports from probe helpers.
