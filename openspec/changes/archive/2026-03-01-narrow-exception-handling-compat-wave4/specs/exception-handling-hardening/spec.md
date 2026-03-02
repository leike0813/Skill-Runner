## MODIFIED Requirements

### Requirement: Broad exception handling MUST be policy-controlled
The policy gate remains mandatory and is tightened for wave4 router-boundary convergence.

#### Scenario: Wave4 baseline ratchet on boundary hotspots
- **WHEN** wave4 reduces broad-catch counts in router/orchestration targets
- **THEN** `docs/contracts/exception_handling_allowlist.yaml` MUST be updated in the same wave to the new lower baseline

#### Scenario: No count regression in touched boundary files
- **WHEN** wave4 touches files already under allowlist governance
- **THEN** file-level and global broad-catch counts MUST NOT exceed the pre-wave4 baseline without explicit compatibility justification

### Requirement: Broad catch MUST preserve diagnosability
Retained broad catches in boundary mappings MUST preserve actionable diagnostics and fallback intent.

#### Scenario: Router internal-error mapping remains standardized
- **WHEN** router handlers keep broad catch for stable HTTP mapping
- **THEN** handlers MUST route through standardized internal-error helpers with structured diagnostics (`component`, `action`, `error_type`, `fallback`)

#### Scenario: Defensive cleanup fallback in orchestration
- **WHEN** orchestration retains best-effort broad catch to avoid masking primary failures
- **THEN** code MUST explicitly document best-effort intent and MUST preserve primary failure semantics

### Requirement: Core runtime and orchestration MUST prioritize narrowing
Wave4 extends narrowing priority from auth core to boundary-heavy router/orchestration hotspots.

#### Scenario: Deterministic validation/parse paths in routers
- **WHEN** broad catches guard deterministic validation, parsing, or conversion paths in `routers/engines.py` and `routers/ui.py`
- **THEN** handlers MUST be narrowed to explicit exception classes while preserving current HTTP contract behavior

#### Scenario: Swallow-style fallback in orchestrator read paths
- **WHEN** touched orchestrator paths include broad-catch silent fallback branches
- **THEN** those branches MUST be removed or converted to typed fallback with explicit diagnostics

### Requirement: Broad-catch governance MUST remain backward compatible
Wave4 hardening remains compatibility-first and cannot change external contracts.

#### Scenario: Existing API/runtime behavior during wave4 narrowing
- **WHEN** wave4 narrows broad catches in router/orchestration paths
- **THEN** public HTTP behavior and runtime contract/invariant behaviors MUST remain unchanged
