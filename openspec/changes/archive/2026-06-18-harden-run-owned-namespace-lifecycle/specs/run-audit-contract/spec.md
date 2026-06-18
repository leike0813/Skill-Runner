# run-audit-contract Delta

## MODIFIED Requirements

### Requirement: New Runs Emit Only Canonical Runtime Files
New request-bound runs MUST emit canonical runtime files under their run-owned namespace when layout metadata exists.

#### Scenario: Request-bound attempt audit uses namespaced audit directory
- **WHEN** an attempt starts for a request-bound run with namespace `<namespace>`
- **THEN** attempt audit files are written under `.audit/<namespace>/`
- **AND** `.audit/stdout.<attempt>.log`, `.audit/stderr.<attempt>.log`, `.audit/io_chunks.<attempt>.jsonl`, `.audit/meta.<attempt>.json`, `.audit/service.<attempt>.log`, `.audit/events.<attempt>.jsonl`, and `.audit/fcmp_events.<attempt>.jsonl` at the root are not written as current truth for that run.

### Requirement: Attempt Audit Files Are History Only
Attempt-scoped audit files MUST remain run history and MUST NOT become current state truth.

#### Scenario: Namespaced audit history does not drive current status
- **WHEN** namespaced audit logs are missing, empty, or partially flushed
- **THEN** current status reads still use the current state projection
- **AND** audit files remain historical evidence only.

### Requirement: Service log mirror MUST remain run-scoped and history-only
Service log mirrors MUST be written to the same audit namespace as the request-bound run.

#### Scenario: Interaction and auth route service logs use namespaced audit
- **WHEN** reply, auth import, or auth status routes open run-scope service log mirrors for a request-bound run
- **THEN** service logs are appended under `.audit/<namespace>/service.run.log`
- **AND** root `.audit/service.run.log` is only used for no-layout legacy paths.

### Requirement: Attempt audit MUST preserve quarantined overflow raw lines
Overflow raw line sidecars MUST be stored in the active audit directory for the attempt.

#### Scenario: Overflow sidecar is namespaced for request-bound run
- **WHEN** runtime quarantines an overflowed line during a request-bound attempt
- **THEN** `overflow_index.<attempt>.jsonl` and `overflow_lines/<attempt>/...` are written under `.audit/<namespace>/`
- **AND** the root `.audit` overflow files are not written for that request-bound attempt.

## ADDED Requirements

### Requirement: Live protocol mirrors MUST use the request-owned audit directory
Live FCMP, RASP, and chat replay mirror writers MUST write to the request-owned audit directory when one is supplied.

#### Scenario: Live FCMP and RASP mirror writes are namespaced
- **WHEN** a request-bound attempt publishes live runtime events
- **THEN** FCMP rows are mirrored to `.audit/<namespace>/fcmp_events.<attempt>.jsonl`
- **AND** RASP rows are mirrored to `.audit/<namespace>/events.<attempt>.jsonl`.

#### Scenario: Chat replay mirror writes are namespaced
- **WHEN** FCMP rows derive chat replay rows for a request-bound run
- **THEN** chat replay rows are mirrored to `.audit/<namespace>/chat_replay.jsonl`.

### Requirement: Output schema contract artifacts MUST use request-owned audit directory
Machine-readable target output schema artifacts MUST be materialized under the request-owned audit directory when layout metadata exists.

#### Scenario: Canonical target schema is namespaced
- **WHEN** a request-bound run materializes its target output schema
- **THEN** the canonical schema is written to `.audit/<namespace>/contracts/target_output_schema.json`
- **AND** `.audit/contracts/target_output_schema.json` at the root is not written as current contract for that run.

#### Scenario: Codex compat schema follows canonical schema directory
- **WHEN** Codex structured-output compatibility translates the target schema
- **THEN** the compat schema is written beside the canonical schema as `.audit/<namespace>/contracts/target_output_schema.codex_compatible.json`
- **AND** Codex CLI schema arguments reference that namespaced relpath.

### Requirement: Interaction and auth audit events MUST use request-owned audit directory
Interaction and auth routes that emit orchestrator audit events MUST use the request-owned audit directory.

#### Scenario: User reply accepted event is namespaced
- **WHEN** a waiting-user request accepts a reply
- **THEN** `interaction.reply.accepted` is written to `.audit/<namespace>/orchestrator_events.<attempt>.jsonl`
- **AND** root `.audit/orchestrator_events.<attempt>.jsonl` is not written as current evidence for that request.

#### Scenario: Auth route callback event is namespaced
- **WHEN** an auth selection, auth submission, auth import, or auth status reconciliation emits an orchestrator event for a request-bound run
- **THEN** the event is written under `.audit/<namespace>/`
- **AND** root `.audit` is only used when no layout metadata exists.
