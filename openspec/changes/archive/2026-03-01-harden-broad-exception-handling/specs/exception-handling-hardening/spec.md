## ADDED Requirements

### Requirement: Broad exception handling MUST be policy-controlled
The system MUST enforce a machine-readable policy for `except Exception` usage across `server/`, and MUST reject unapproved broad catches in CI.

#### Scenario: New broad catch is introduced without approval
- **WHEN** a new `except Exception` appears in a file not covered by the allowlist baseline
- **THEN** policy test MUST fail with file path and mismatch details

#### Scenario: Broad catch count exceeds approved baseline
- **WHEN** `except Exception` count in an allowlisted file exceeds approved baseline
- **THEN** policy test MUST fail and require policy update with explicit justification

### Requirement: Broad catch MUST preserve diagnosability
Where broad catch is retained for compatibility or third-party boundaries, the handling MUST preserve diagnosability through explicit context and fallback semantics.

#### Scenario: Best-effort cleanup failure
- **WHEN** a best-effort cleanup path catches broad exceptions
- **THEN** code MUST preserve primary flow and MUST emit diagnosable context (code comment and/or structured log)

### Requirement: Core runtime and orchestration MUST prioritize narrowing
Core runtime/orchestration modules MUST prioritize replacing broad catches with specific exception types when behavior can be preserved.

#### Scenario: Type conversion fallback
- **WHEN** code catches broad exceptions only to handle parse failures
- **THEN** it MUST be narrowed to `TypeError` and/or `ValueError`

#### Scenario: JSON or file parsing fallback
- **WHEN** code catches broad exceptions around JSON/file loading
- **THEN** it MUST be narrowed to parsing and I/O related exceptions where feasible

### Requirement: Broad-catch governance MUST remain backward compatible
Hardening MUST NOT introduce public API breaking changes or runtime contract/invariant changes.

#### Scenario: Existing API behavior during hardening
- **WHEN** broad catch logic is narrowed or policy-governed
- **THEN** public HTTP API contracts and runtime schema/invariants MUST remain unchanged
