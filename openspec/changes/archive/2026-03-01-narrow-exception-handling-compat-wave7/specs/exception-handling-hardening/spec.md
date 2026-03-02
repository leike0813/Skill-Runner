## MODIFIED Requirements

### Requirement: Broad exception handling MUST be policy-controlled
Allowlist governance remains mandatory and is tightened for wave7 adapter-config and skill-package hotspots.

#### Scenario: Wave7 baseline ratchet on targeted hotspots
- **WHEN** wave7 reduces broad-catch counts in `iflow/gemini config_composer`, `codex toml_manager`, and `skill_package_manager`
- **THEN** `docs/contracts/exception_handling_allowlist.yaml` MUST be updated in the same wave to the new lower baseline

#### Scenario: No silent regression in touched files
- **WHEN** wave7 modifies files already under broad-catch governance
- **THEN** file-level and global broad-catch counts MUST NOT exceed pre-wave7 baseline without explicit compatibility justification

### Requirement: Core runtime and orchestration MUST prioritize narrowing
Wave7 extends deterministic narrowing to engine config composition and skill package management support paths.

#### Scenario: Engine config deterministic parse/compose paths
- **WHEN** broad catches guard deterministic config parsing/composition branches in `iflow` or `gemini` adapter config composers
- **THEN** handlers MUST be narrowed to explicit exception classes while preserving existing config fallback behavior

#### Scenario: Codex TOML deterministic load/save paths
- **WHEN** broad catches guard deterministic TOML parsing or file IO branches in codex TOML manager
- **THEN** handlers MUST be narrowed to explicit TOML/file exception classes while preserving backward-compatible config behavior

#### Scenario: Skill package manager deterministic record/install paths
- **WHEN** broad catches guard deterministic package metadata parsing, state record conversion, or install path handling
- **THEN** handlers MUST be narrowed to explicit exception classes while preserving existing install/fallback semantics

### Requirement: Broad catch MUST preserve diagnosability
Any retained broad catch for uncertain boundaries MUST preserve actionable diagnostics and explicit fallback intent.

#### Scenario: Boundary fallback in package or adapter integration
- **WHEN** package manager or adapter code retains broad catch for non-deterministic boundary uncertainty
- **THEN** handlers MUST emit structured diagnostics (`component`, `action`, `error_type`, `fallback`) and preserve non-breaking fallback behavior

### Requirement: Broad-catch governance MUST remain backward compatible
Wave7 hardening remains compatibility-first and cannot change external contracts.

#### Scenario: Existing API/runtime behavior during wave7 narrowing
- **WHEN** wave7 narrows broad catches in adapter config and skill package support paths
- **THEN** public HTTP behavior and runtime contract/invariant behaviors MUST remain unchanged
