## MODIFIED Requirements

### Requirement: Broad exception handling MUST be policy-controlled
The governance policy remains mandatory and is tightened for iterative hardening waves.

#### Scenario: Wave-level baseline ratchet
- **WHEN** a hardening wave reduces broad-catch counts in targeted files
- **THEN** `docs/contracts/exception_handling_allowlist.yaml` MUST be updated in the same wave so baseline does not drift upward

#### Scenario: No silent baseline expansion
- **WHEN** broad catches are retained in touched files
- **THEN** they MUST remain at or below the previous baseline unless explicitly justified as a compatibility exception

### Requirement: Broad catch MUST preserve diagnosability
Retained broad catches must continue to expose actionable diagnostics and explicit fallback intent.

#### Scenario: Boundary mapping in hotspot modules
- **WHEN** router/adapter boundaries retain broad catches for compatibility
- **THEN** handlers MUST include structured diagnostics (`component`, `action`, `error_type`, `fallback`)

#### Scenario: Best-effort cleanup in runtime/auth flows
- **WHEN** cleanup paths retain broad catches
- **THEN** code MUST document best-effort semantics and MUST NOT mask the primary exception

### Requirement: Core runtime and orchestration MUST prioritize narrowing
The narrowing rule is extended from initial core paths to remaining hotspot modules in this wave.

#### Scenario: Deterministic parse/convert/system-call paths
- **WHEN** broad catches guard deterministic type/parse/system-call operations
- **THEN** they MUST be narrowed to explicit exception classes (for example `TypeError`, `ValueError`, `OverflowError`, `json.JSONDecodeError`, `OSError`) while preserving behavior

#### Scenario: Swallow-first branches in hotspot files
- **WHEN** touched hotspot files contain `pass`/silent-return broad-catch branches
- **THEN** those branches MUST be removed or converted to typed fallback paths with explicit diagnostics

### Requirement: Broad-catch governance MUST remain backward compatible
Wave-2 hardening remains compatibility-first and must not alter external contracts.

#### Scenario: Existing failure-path compatibility during narrowing
- **WHEN** handlers are narrowed or refactored in runtime/auth/engine protocol paths
- **THEN** HTTP/API failure semantics and runtime contract/invariant behaviors MUST remain unchanged
