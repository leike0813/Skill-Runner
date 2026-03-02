## MODIFIED Requirements

### Requirement: Broad exception handling MUST be policy-controlled
Allowlist governance remains mandatory and is tightened for wave6 runtime/skill/adapter residual hotspots.

#### Scenario: Wave6 baseline ratchet on targeted hotspots
- **WHEN** wave6 reduces broad-catch counts in `run_observability` / `skill_patcher` / `trust_folder_strategy` modules
- **THEN** `docs/contracts/exception_handling_allowlist.yaml` MUST be updated in the same wave to the new lower baseline

#### Scenario: No silent expansion in touched files
- **WHEN** wave6 modifies files already governed by allowlist
- **THEN** file-level and global broad-catch counts MUST NOT exceed pre-wave6 baseline without explicit compatibility justification

### Requirement: Core runtime and orchestration MUST prioritize narrowing
Wave6 extends deterministic narrowing to runtime observability and skill/adapter support paths.

#### Scenario: Runtime observability deterministic parse and IO paths
- **WHEN** broad catches guard deterministic file IO / JSON parsing / history materialization paths in `server/runtime/observability/run_observability.py`
- **THEN** handlers MUST be narrowed to explicit exception classes while preserving legacy history/cursor behavior

#### Scenario: Skill patch pipeline deterministic failures
- **WHEN** broad catches guard deterministic parsing, rendering, or patch composition branches in `server/services/skill/skill_patcher.py`
- **THEN** handlers MUST be narrowed to explicit exception classes and preserve existing patch result/fallback semantics

#### Scenario: Trust folder strategy deterministic path handling
- **WHEN** broad catches guard deterministic path normalization and filesystem checks in codex/gemini trust-folder strategy modules
- **THEN** handlers MUST be narrowed to explicit path/IO exception classes while preserving trust policy behavior

### Requirement: Broad catch MUST preserve diagnosability
Any retained broad catch for uncertain boundaries MUST expose explicit diagnostics and fallback intent.

#### Scenario: Runtime compatibility fallback remains observable
- **WHEN** runtime observability retains a broad catch for backward-compatible data parsing
- **THEN** the handler MUST provide structured diagnostics (`component`, `action`, `error_type`, `fallback`) and keep non-blocking behavior

#### Scenario: Third-party or boundary-driven fallback in skill/adapter paths
- **WHEN** skill/adapter code retains broad catch for non-deterministic boundary uncertainty
- **THEN** code MUST document best-effort intent and preserve root-cause traceability

### Requirement: Broad-catch governance MUST remain backward compatible
Wave6 hardening remains compatibility-first and cannot change external contracts.

#### Scenario: Existing API/runtime behavior during wave6 narrowing
- **WHEN** wave6 narrows broad catches in runtime observability and skill/adapter support paths
- **THEN** public HTTP behavior and runtime contract/invariant behaviors MUST remain unchanged
