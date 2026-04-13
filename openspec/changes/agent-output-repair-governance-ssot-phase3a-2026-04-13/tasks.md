## 1. OpenSpec Change Artifacts

- [x] 1.1 Add proposal/design/tasks for the phase 3A repair-governance slice.
- [x] 1.2 Add delta specs for `output-json-repair`, `interactive-run-lifecycle`, `interactive-decision-policy`, `interactive-engine-turn-protocol`, and `run-audit-contract`.

## 2. Machine Contracts

- [x] 2.1 Upgrade `server/contracts/invariants/agent_output_protocol_invariants.yaml` with the attempt/internal-round model, single-executor ownership, pipeline ordering, repair-event requirements, and repair-audit requirements.
- [x] 2.2 Extend `server/contracts/schemas/runtime_contract.schema.json` with additive orchestrator repair event types and canonical payload constraints.

## 3. Main Documentation Sync

- [x] 3.1 Add `docs/output_repair_governance_ssot.md` as the dedicated repair governance anchor.
- [x] 3.2 Update `docs/session_runtime_statechart_ssot.md`, `docs/session_event_flow_sequence_fcmp.md`, `docs/runtime_stream_protocol.md`, `docs/runtime_event_schema_contract.md`, and `docs/run_artifacts.md` to align with the unified repair model and mark legacy behaviors explicitly.

## 4. Validation

- [x] 4.1 Update or add contract guard tests for the invariant file and runtime schema repair events.
- [x] 4.2 Run `openspec status --change agent-output-repair-governance-ssot-phase3a-2026-04-13 --json`.
- [x] 4.3 Run `openspec instructions apply --change agent-output-repair-governance-ssot-phase3a-2026-04-13 --json`.
- [x] 4.4 Run targeted pytest and mypy checks for the changed contract surface.
- [x] 4.5 Grep docs/specs for legacy repair wording to confirm the governance model is unified and legacy labels are explicit.
