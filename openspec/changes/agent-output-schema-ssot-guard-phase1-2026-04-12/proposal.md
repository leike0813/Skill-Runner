## Why

Current agent output handling still treats structured output as a soft convention rather than a runtime contract. This leaves `interactive` behavior split across `__SKILL_DONE__`, soft completion, and `<ASK_USER_YAML>`, which makes later implementation of JSON-only enforcement ambiguous and hard to audit.

## What Changes

- Establish a spec-first JSON-only output contract for both `auto` and `interactive` modes before any runtime implementation changes.
- Define `interactive` output as a single union contract with explicit final and pending branches.
- Define repair retries as same-attempt internal rounds with explicit audit expectations and fallback boundaries.
- Deprecate `<ASK_USER_YAML>` as a legacy compatibility semantic rather than a valid primary protocol.
- Add an independent machine-readable invariant contract plus test guards for the new output protocol.
- Reposition `server/contracts/schemas/ask_user.schema.yaml` as a `ui_hints` capability source instead of a YAML block protocol definition.

## Capabilities

### New Capabilities
- `n/a`

### Modified Capabilities
- `interactive-engine-turn-protocol`: Replace YAML-first ask-user semantics with JSON-only output contract semantics and explicit legacy deprecation.
- `interactive-run-lifecycle`: Replace soft-completion-first waiting logic with union-schema-driven final vs pending output semantics.
- `interactive-decision-policy`: Update completion-evidence priority to explicit final/pending JSON branches and same-attempt repair retries.
- `output-json-repair`: Define schema repair as same-attempt internal convergence for both modes, with bounded retries and fallback-after-exhaustion.
- `skill-patch-modular-injection`: Reframe interactive patching around JSON-only output contracts and legacy `<ASK_USER_YAML>` deprecation.

## Impact

- New OpenSpec change artifacts under `openspec/changes/agent-output-schema-ssot-guard-phase1-2026-04-12/`.
- New machine-readable invariant contract at `server/contracts/invariants/agent_output_protocol_invariants.yaml`.
- New guard helpers and tests under `tests/common/` and `tests/unit/`.
- `server/contracts/schemas/ask_user.schema.yaml` will change role but not public API shape.
- No FCMP, RASP, HTTP API, or runtime implementation changes in this slice.
