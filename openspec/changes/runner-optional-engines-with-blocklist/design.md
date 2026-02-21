## Context

Engine compatibility for skills is currently modeled as a required non-empty `runner.json.engines` list and validated in multiple layers. This causes two issues:
1. Authoring friction for skills that conceptually support most engines with a small deny list.
2. Repeated engine validation logic across request routers and workspace orchestration, which increases drift risk.

The change must keep install-time and temporary-skill behavior consistent and enforce strict validation for unknown engine names and contradictory declarations.

## Goals / Non-Goals

**Goals:**
- Introduce optional `unsupported_engines` in `runner.json`.
- Allow missing/empty `engines` by defaulting to all supported engines (`codex`, `gemini`, `iflow`).
- Reject invalid engine contracts early (unknown names, overlap, effective empty set).
- Centralize effective-engine resolution so runtime and validation paths share one rule set.

**Non-Goals:**
- Adding new runtime engines.
- Changing model-level selection/validation behavior.
- Altering unrelated manifest fields (`schemas`, `artifacts`, `version`, identity checks).

## Decisions

1. Decision: Define a single effective-engine algorithm for manifest validation and runtime checks.
   - Rule:
   - Base set = `engines` when provided and non-empty; otherwise all supported engines.
   - Subtract `unsupported_engines` from base set.
   - Validate: unknown names forbidden in both fields; overlap forbidden; resulting set must be non-empty.
   - Rationale: one deterministic contract avoids ambiguity and maps directly to user intent ("allowlist with optional blocklist" or "default all then blocklist").
   - Alternative considered: keep separate install-time and runtime logic. Rejected due to drift and inconsistent error behavior.

2. Decision: Keep public `SkillManifest.engines` as the effective set after resolution.
   - Rationale: existing runtime call sites already consume `skill.engines`; preserving that shape minimizes blast radius.
   - Alternative considered: add a second field (e.g., `resolved_engines`). Rejected to avoid broad model/API churn.

3. Decision: Fail fast during package validation/staging for effective-empty engine sets.
   - Rationale: a non-runnable skill package is invalid by definition and should not proceed to execution setup.
   - Alternative considered: allow installation and fail only when run is requested. Rejected per product rule and poorer UX.

## Risks / Trade-offs

- [Risk] Centralizing validation changes error text surfaced by multiple APIs.
  - Mitigation: keep explicit, deterministic error messages and update related tests together.
- [Risk] Existing skill fixtures relying on implicit required `engines` may become semantically different.
  - Mitigation: adjust fixtures/tests to assert new defaulting and rejection semantics.
- [Risk] Temporary skill and installed skill flows could diverge if one bypasses shared resolution.
  - Mitigation: route both through the same validator helper and remove duplicate router-level checks.

## Migration Plan

1. Update OpenSpec delta requirements for `skill-package-install` and `ephemeral-skill-validation`.
2. Implement shared engine-resolution validation helper in service layer and apply to both install and temp-skill staging.
3. Replace duplicated runtime checks with helper-backed checks that consume resolved `skill.engines`.
4. Update/extend unit tests for unknown names, overlap, default-all, and effective-empty rejection.
5. Validate with mypy and targeted tests; rollback by reverting change set if regression appears.

## Open Questions

- None. Product rules for field naming and validation outcomes are finalized in this change.
