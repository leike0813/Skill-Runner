## MODIFIED Requirements

### Requirement: Broad exception handling MUST be policy-controlled
The allowlist policy remains mandatory and is tightened for wave5 platform/orchestration residual hotspots.

#### Scenario: Wave5 baseline ratchet on residual hotspots
- **WHEN** wave5 reduces broad-catch counts in `schema_validator` / `agent_cli_manager` / `run_audit_service`
- **THEN** `docs/contracts/exception_handling_allowlist.yaml` MUST be updated in the same wave to the new lower baseline

#### Scenario: No silent regression in touched files
- **WHEN** wave5 touches files already under broad-catch governance
- **THEN** file-level and global broad-catch counts MUST NOT exceed the pre-wave5 baseline without explicit compatibility justification

### Requirement: Core runtime and orchestration MUST prioritize narrowing
Wave5 extends deterministic narrowing from boundary-heavy modules to platform validation and orchestration support paths.

#### Scenario: Deterministic schema parse and validation paths
- **WHEN** broad catches guard schema file IO/JSON parsing/validation branches in `server/services/platform/schema_validator.py`
- **THEN** handlers MUST be narrowed to explicit exception classes (for example `OSError`, `json.JSONDecodeError`, typed validation errors) while preserving existing returned-error semantics

#### Scenario: Deterministic bootstrap and settings parsing paths
- **WHEN** broad catches guard bootstrap config loading and settings/path normalization in `server/services/orchestration/agent_cli_manager.py`
- **THEN** handlers MUST be narrowed to explicit exception classes and preserve current fallback behavior for managed runtime bootstrap

#### Scenario: Audit event replay and sequence parse paths
- **WHEN** broad catches guard audit JSONL parsing and event sequence reconstruction in `server/services/orchestration/run_audit_service.py`
- **THEN** handlers MUST be narrowed to explicit parse/IO exception classes while preserving legacy history compatibility behavior

### Requirement: Broad catch MUST preserve diagnosability
Any broad catch retained for compatibility boundaries MUST preserve actionable diagnostics and explicit fallback intent.

#### Scenario: Third-party adapter parse compatibility
- **WHEN** runtime stream parsing in `run_audit_service` retains a broad catch due to adapter-boundary uncertainty
- **THEN** the handler MUST log structured diagnostics (`component`, `action`, `error_type`, `fallback`) and MUST keep non-blocking fallback semantics

#### Scenario: Compatibility fallback in orchestration bootstrap
- **WHEN** `agent_cli_manager` retains broad catch in best-effort compatibility branches
- **THEN** code MUST include explicit best-effort intent and preserve diagnostics needed for root-cause tracing

### Requirement: Broad-catch governance MUST remain backward compatible
Wave5 hardening remains compatibility-first and cannot change external contracts.

#### Scenario: Existing API/runtime behavior during wave5 narrowing
- **WHEN** wave5 narrows broad catches in platform/orchestration support modules
- **THEN** public HTTP behavior and runtime contract/invariant behaviors MUST remain unchanged
