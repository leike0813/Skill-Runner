## Context

The repository already has the right high-level pieces:

- canonical run-scoped machine schema materialization
- structured-output compat translation for engines such as Codex
- runtime `SKILL.md` patching
- repair prompts for same-attempt output convergence

The problem is that the text side of the contract is still over-materialized and duplicated. Canonical `.json` schema is the real machine truth, but runtime also writes prompt-facing `.md` artifacts, mode templates still restate contract details, and repair prompts read a separate prompt summary path. That model introduces multiple derived text surfaces without clear ownership.

## Goals / Non-Goals

**Goals:**
- Keep canonical `.json` schema as the single persisted machine truth.
- Remove run-scoped prompt-facing `.md` output-contract artifacts.
- Make runtime `SKILL.md` the only agent-facing text contract sink.
- Reuse one dynamic contract builder for `SKILL.md` injection and repair prompts.
- Keep engine-specific compat translation aligned across CLI schema injection and prompt contract wording.
- Preserve the user-edited intent of existing static templates, especially `patch_output_format_contract.md` and `patch_mode_auto.md`.

**Non-Goals:**
- Do not change HTTP/FCMP/RASP/public runtime shapes.
- Do not change canonical schema semantics.
- Do not collapse all static templates into one file.
- Do not remove canonical `.json` compat artifacts that engines still need for CLI transport.

## Decisions

### 1. Persist only machine schema artifacts

Canonical `.json` artifacts remain on disk because validation, adapter CLI injection, and audit debugging need them. Prompt-facing `.md` artifacts are removed because they add a second persistence surface for derived text without adding truth.

Alternative considered:
- Keep `.md` artifacts for audit readability.
Why rejected:
- Audit readability is already covered by patched `SKILL.md` plus repair prompt logs, while separate `.md` artifacts increase drift risk.

### 2. Use one dynamic contract builder for both SKILL injection and repair prompts

`skill_patch_output_schema.py` becomes the single renderer for field-level contract text. `SKILL.md` injection and repair prompts both consume this output.

Alternative considered:
- Keep a lightweight `.md` summary builder for repair only.
Why rejected:
- It recreates a parallel wording source and reintroduces the same drift problem this change is supposed to eliminate.

### 3. Re-scope interactive mode template to policy only

`patch_mode_interactive.md` now expresses interaction policy:

- proceed autonomously when possible
- ask at most one question per turn
- choose final or pending, never both

Field-level details for `message`, `ui_hints`, `options`, and `files` live only in the dynamic contract section.

Alternative considered:
- Keep a short pending-branch placeholder block in the mode template.
Why rejected:
- Even a small placeholder creates a second semantic surface for the same branch contract.

### 4. Keep structured-output pipeline as the prompt/schema alignment owner

`structured_output_pipeline` already decides whether an engine consumes canonical or compat-translated machine schema. This change extends that ownership to prompt-contract rendering as well.

Alternative considered:
- Let `skill_patcher` choose canonical vs compat wording independently.
Why rejected:
- It would allow CLI schema and prompt wording to drift again.

## Risks / Trade-offs

- [Risk] Existing tests and docs are heavily coupled to `.md` artifact paths. → Mitigation: update targeted tests and provide a dedicated SSOT doc that clearly replaces the old model.
- [Risk] Renaming contract markers could create noisy churn. → Mitigation: keep the patch plan shape stable and only rename the dynamic section marker where it materially improves clarity.
- [Risk] Repair prompt wording may change subtly when it stops loading persisted `.md` files. → Mitigation: reuse the same dynamic builder used for `SKILL.md` injection and keep tests around convergence prompt behavior.

## Migration Plan

1. Remove prompt-summary path fields from schema materialization and structured-output artifact types.
2. Stop writing run-scoped `.md` prompt-summary artifacts.
3. Rewire `skill_patcher` and `run_output_convergence_service` to consume in-memory dynamic contract text.
4. Rewrite `patch_mode_interactive.md` as policy-only.
5. Update tests and docs to lock the new model.

## Open Questions

- None for this slice. Canonical schema persistence, dynamic contract reuse, and interactive mode template scope are already locked by the change boundary.
