## MODIFIED Requirements

### Requirement: Broad exception handling MUST be policy-controlled
The governance policy remains mandatory and is further tightened for wave3 hotspot convergence.

#### Scenario: Wave3 baseline ratchet
- **WHEN** wave3 reduces broad-catch counts in targeted runtime/auth modules
- **THEN** `docs/contracts/exception_handling_allowlist.yaml` MUST be updated in the same wave to the new lower baseline

#### Scenario: No silent re-expansion in touched hotspots
- **WHEN** touched hotspot files still retain broad catches for compatibility
- **THEN** file-level and global counts MUST NOT exceed the pre-wave3 baseline unless explicitly justified and reviewed

### Requirement: Core runtime and orchestration MUST prioritize narrowing
Narrowing priority is extended to engine auth orchestration/runtime hotspots in wave3.

#### Scenario: Engine auth runtime deterministic failure paths
- **WHEN** broad catch guards deterministic conversion/validation/cleanup paths in `engine_auth_flow_manager` or engine `runtime_handler` modules
- **THEN** handlers MUST be narrowed to explicit exception classes while preserving existing fallback semantics

#### Scenario: Swallow-style branches in targeted auth files
- **WHEN** wave3-target files contain broad-catch `pass` or silent-return branches
- **THEN** those branches MUST be removed or replaced with typed fallback paths that keep compatibility and improve diagnosability

### Requirement: Broad catch MUST preserve diagnosability
Retained broad catches in boundary and best-effort paths MUST remain explainable and traceable.

#### Scenario: Runtime/auth best-effort cleanup retention
- **WHEN** runtime/auth cleanup logic keeps a broad catch to avoid masking primary failures
- **THEN** code MUST include explicit best-effort intent and MUST preserve actionable diagnostics (at least `component`, `action`, `error_type`, `fallback`)

#### Scenario: Router boundary mapping remains compatible
- **WHEN** router boundary handlers retain broad catches for stable error mapping
- **THEN** they MUST route through standardized internal-error helpers with structured diagnostics and unchanged HTTP semantics

### Requirement: Broad-catch governance MUST remain backward compatible
Wave3 hardening remains compatibility-first and must not change external contracts.

#### Scenario: Existing API/runtime behavior during wave3 narrowing
- **WHEN** wave3 narrows handlers in runtime/auth/orchestration paths
- **THEN** public HTTP behavior and runtime contract/invariant behaviors MUST remain unchanged
