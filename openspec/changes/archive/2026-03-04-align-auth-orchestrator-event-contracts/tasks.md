## 1. Schema Contract Alignment

- [x] 1.1 Audit the canonical payload fields for `auth.session.created`, `auth.method.selected`, `auth.session.busy`, `auth.input.accepted`, `auth.session.completed`, `auth.session.failed`, and `auth.session.timed_out`.
- [x] 1.2 Update `server/assets/schemas/protocol/runtime_contract.schema.json` so the audited auth orchestrator event payloads are accepted and undeclared extra fields remain rejected.

## 2. Orchestration Implementation

- [x] 2.1 Refactor `server/services/orchestration/run_auth_orchestration_service.py` to emit auth orchestrator events through a unified payload contract.
- [x] 2.2 Verify `server/services/orchestration/run_audit_service.py` still performs strict schema validation and surfaces auth event contract violations clearly.

## 3. Documentation and Specs

- [x] 3.1 Update `docs/runtime_event_schema_contract.md` to document the aligned auth orchestrator event fields and callback/code submit semantics.
- [x] 3.2 Sync the modified capability specs for `runtime-event-command-schema`, `interactive-job-api`, and `job-orchestrator-modularization` with the aligned auth event contract.

## 4. Regression Coverage

- [x] 4.1 Add schema registry tests covering the full auth orchestrator event set, including `auth.input.accepted.accepted_at`.
- [x] 4.2 Add auth orchestration tests proving callback/code submission writes schema-valid `auth.input.accepted` events and does not fail with `500`.
- [x] 4.3 Add or extend integration coverage for the callback URL submit path so accepted auth input continues into the auth flow.
