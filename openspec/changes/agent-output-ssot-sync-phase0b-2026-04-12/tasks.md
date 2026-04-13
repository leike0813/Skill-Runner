## 1. OpenSpec Change Artifacts

- [x] 1.1 Add proposal/design/tasks for the phase 0B SSOT sync slice.
- [x] 1.2 Add delta specs for `interactive-engine-turn-protocol`, `interactive-run-lifecycle`, `interactive-decision-policy`, `output-json-repair`, `skill-patch-modular-injection`, and `interactive-job-api`.

## 2. Main Documentation Sync

- [x] 2.1 Update `docs/api_reference.md` to remove YAML-first protocol wording and align interactive completion/waiting semantics to the union contract.
- [x] 2.2 Update `docs/session_runtime_statechart_ssot.md`, `docs/session_event_flow_sequence_fcmp.md`, and `docs/runtime_stream_protocol.md` to describe pending JSON as the target waiting-user source.
- [x] 2.3 Update `docs/misc/GUIDE_output_schema_generation.md`, `docs/dev_guide.md`, and `docs/autoskill_package_guide.md` to describe materialized schema artifacts and mark legacy soft-completion / ask-user behavior as deprecated rollout context only.

## 3. Validation

- [x] 3.1 Run `openspec status --change agent-output-ssot-sync-phase0b-2026-04-12 --json`.
- [x] 3.2 Run `openspec instructions apply --change agent-output-ssot-sync-phase0b-2026-04-12 --json`.
- [x] 3.3 Grep the updated docs and change files for `<ASK_USER_YAML>` and soft-completion language to confirm they are no longer presented as the formal protocol.
