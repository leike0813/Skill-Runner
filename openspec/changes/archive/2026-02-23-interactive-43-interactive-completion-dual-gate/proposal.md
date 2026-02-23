## Why

Interactive execution currently depends on LLM-generated `ask_user` JSON shape for critical control-flow decisions.
This is fragile and can fail due to format drift (for example non-numeric `interaction_id`, partial payloads, or free-form assistant text).

We need to make the lifecycle gate deterministic:

- In `interactive` mode, completion should be dual-track:
  - strong evidence: `__SKILL_DONE__`;
  - soft evidence: no marker but output passes schema validation.
- In `auto` mode, completion does not strictly depend on `__SKILL_DONE__`; valid final output is sufficient.
- `ask_user` is optional enrichment only, not a hard gate.
- `interactive` mode should support `runner.json.max_attempt` to prevent unbounded loops.

## What Changes

- Remove interactive patch requirement that forces agent to emit structured `ask_user`.
- Refactor run lifecycle gating to be mode-aware:
  - `interactive`: strong+soft completion gate.
  - `auto`: output-validation-driven completion gate.
- Ensure `__SKILL_DONE__` is ignored during output validation in both modes.
- Keep `ask_user` parsing as optional metadata enrichment (`ui_hints/context`) without allowing malformed `ask_user` to fail runs.
- Switch optional `ask_user` hints to non-JSON structured payload (YAML block) to avoid being mis-parsed as final output when output schema is permissive.
- `ask_user` hints (including YAML form) remain enrichment-only and MUST NOT become lifecycle control predicates.
- Add optional `runner.json.max_attempt` (`integer`, `>=1`) and enforce:
  - only for `interactive`;
  - if `attempt_number >= max_attempt` and no completion evidence in current turn, mark run failed.
- Add stable diagnostics:
  - warning: `INTERACTIVE_COMPLETED_WITHOUT_DONE_MARKER`;
  - error: `INTERACTIVE_MAX_ATTEMPT_EXCEEDED`.
- Normalize done-marker stream detection to handle both plain JSON and escaped NDJSON string payload forms (for example `\"__SKILL_DONE__\": true` inside runtime event rows).
- Enforce terminal precedence: if done marker is detected but output parsing/schema validation fails, run MUST fail (not `waiting_user`).
- Align backend, protocol translation, UI/E2E client, and docs with the new contract.

## Naming

This change is named `interactive-43-interactive-completion-dual-gate` to reflect the final dual-track completion policy.

## Capabilities

### Modified Capabilities
- `interactive-engine-turn-protocol`
- `interactive-run-lifecycle`
- `interactive-job-api`
- `interactive-decision-policy`
- `run-observability-ui`
- `builtin-e2e-example-client`
- `skill-package-validation-schema`

## Impact

- Affected code (expected):
  - `server/services/job_orchestrator.py`
  - `server/services/skill_patcher.py`
  - `server/services/runtime_event_protocol.py`
  - `server/services/run_interaction_service.py` (if pending payload normalization is adjusted)
  - `server/assets/templates/ui/run_detail.html`
  - `e2e_client/templates/run_observe.html`
- Affected docs:
  - `docs/runtime_stream_protocol.md`
  - `docs/api_reference.md`
  - `docs/dev_guide.md`
