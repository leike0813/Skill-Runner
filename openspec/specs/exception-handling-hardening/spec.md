# exception-handling-hardening Specification

## Purpose
TBD - created by archiving change harden-broad-exception-handling. Update Purpose after archive.
## Requirements
### Requirement: Broad exception handling MUST be policy-controlled
Allowlist governance remains mandatory and is elevated to closeout mode in wave8.

#### Scenario: Wave8 closeout baseline ratchet
- **WHEN** wave8 performs full residual broad-catch sweep in `server/`
- **THEN** `docs/contracts/exception_handling_allowlist.yaml` MUST be updated in the same wave to the new lower baseline

#### Scenario: No post-closeout regression
- **WHEN** wave8 completes and subsequent changes touch governed files
- **THEN** file-level and global broad-catch counts MUST NOT exceed wave8 baseline without explicit compatibility approval

### Requirement: Broad catch MUST preserve diagnosability
Wave8 closeout MUST leave only auditable broad catches for truly uncertain boundaries.

#### Scenario: Residual broad catch is explicitly justified
- **WHEN** a broad catch remains after wave8
- **THEN** it MUST include clear compatibility rationale and structured diagnostics (`component`, `action`, `error_type`, `fallback`)

#### Scenario: Residual broad catch maps to approved context only
- **WHEN** wave8 finalizes remaining broad catches
- **THEN** each retained site MUST map to approved contexts (`boundary_mapping`, `best_effort_cleanup`, `observability_non_blocking`, `third_party_boundary`)

#### Scenario: Management routes stay within allowlist
- **WHEN** management routes handle system settings, reset actions, or engine list/detail boundaries
- **THEN** they MUST narrow `except Exception` to specific exception families or remove it entirely
- **AND** any retained best-effort boundary fallback MUST include structured logging and explicit fallback behavior
- **AND** the change MUST NOT increase global or per-file allowlist totals

### Requirement: Core runtime and orchestration MUST prioritize narrowing
Wave8 MUST clear all remaining narrowable swallow-style broad catches in one pass.

#### Scenario: Swallow-style residuals are eliminated
- **WHEN** residual broad catches in wave8-target files use `pass`, `continue/break`, silent `return`, or non-diagnostic fallback
- **THEN** they MUST be replaced with typed exceptions or explicit compatible fallback paths with diagnostics

#### Scenario: Deterministic parse/IO/type-convert residuals are narrowed
- **WHEN** residual broad catches guard deterministic parse/IO/type-conversion logic
- **THEN** handlers MUST be narrowed to explicit exception classes while preserving current behavior

### Requirement: Broad-catch governance MUST remain backward compatible
Wave8 remains compatibility-first despite closeout scope.

#### Scenario: Existing API/runtime behavior during closeout sweep
- **WHEN** wave8 narrows or reclassifies residual broad catches across auth/router/orchestration/platform/skill modules
- **THEN** public HTTP behavior and runtime contract/invariant behaviors MUST remain unchanged
