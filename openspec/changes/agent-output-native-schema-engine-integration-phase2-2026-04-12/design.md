## Context

The repository already has the prerequisites for native engine schema enforcement:

- phase 0A defined the JSON-only output contract and the pending/final branch model
- phase 1 materialized a stable run-scoped machine schema at `.audit/contracts/target_output_schema.json`
- `run_job_lifecycle_service` already propagates the stable schema relpath through internal `run_options`
- the base execution adapter already persists first-attempt spawn-command audit fields into `.audit/request_input.json`

What is missing is the final dispatch hop. Claude and Codex command builders still ignore the materialized schema artifact, so the headless execution path does not benefit from native CLI schema constraints.

## Goals / Non-Goals

**Goals**
- Pass the run-scoped schema artifact into Claude and Codex headless start/resume commands.
- Preserve start/resume symmetry for both engines.
- Keep native schema dispatch observable through existing first-attempt spawn-command audit.
- Avoid duplicating schema-path parsing logic across command builders.

**Non-Goals**
- Do not modify orchestrator repair behavior, result fallback, or completion/waiting decisions.
- Do not change `PendingInteraction`, `ASK_USER_YAML` extraction, or interactive pending projection.
- Do not add new request-input audit fields or public protocol fields.
- Do not modify UI-shell command behavior in this phase.

## Decisions

### Decision 1: Reuse the existing run option without introducing a second schema-path channel
Command builders consume `__target_output_schema_relpath` directly.

Why:
- The path is already written by phase 1 materialization.
- Start and resume already share the same `options` channel.
- A second schema-path option would create unnecessary drift.

### Decision 2: Headless Claude defaults move to `--output-format json`
Claude headless `start` and `resume` profile defaults use `json`, then append `--json-schema <relpath>` when a materialized schema relpath exists.

Why:
- The implementation plan explicitly fixes Claude to `--output-format json + --json-schema`.
- This aligns the CLI contract with the JSON-only target direction.

### Decision 3: Passthrough commands remain caller-owned
When `passthrough_args` or `__passthrough_cli_args` are provided, builders do not inject schema arguments.

Why:
- Passthrough mode is the escape hatch for harness-controlled command construction.
- Auto-injecting schema flags into passthrough commands would violate existing ownership boundaries.

### Decision 4: Existing spawn-command audit remains the SSOT for command observability
No new audit fields are added. Validation relies on `spawn_command_original_first_attempt` and `spawn_command_effective_first_attempt`.

Why:
- The base adapter already persists both command views for the first attempt.
- The requirement is observability of the launched command, not a second schema-specific audit layer.

## Implementation Outline

1. Add a small shared helper in `server/runtime/adapter/common/` that resolves the schema relpath from `options` and emits engine-specific CLI fragments.
2. Update Claude profile defaults from `stream-json` to `json` for headless `start/resume`.
3. Update Claude command builder to append `--json-schema <relpath>` for non-passthrough start/resume commands.
4. Update Codex command builder to append `--output-schema <relpath>` for non-passthrough start/resume commands.
5. Add/adjust tests at two levels:
   - builder/profile level for command shape and ordering
   - adapter level for first-attempt spawn-command audit persistence

## Validation Plan

- `openspec status --change agent-output-native-schema-engine-integration-phase2-2026-04-12 --json`
- `openspec instructions apply --change agent-output-native-schema-engine-integration-phase2-2026-04-12 --json`
- Targeted pytest suites for:
  - `tests/unit/test_adapter_command_profiles.py`
  - `tests/unit/test_adapter_parsing.py`
  - `tests/unit/test_codex_adapter.py`
  - `tests/unit/test_claude_adapter.py`
- `mypy` on the new helper and the touched command builders
