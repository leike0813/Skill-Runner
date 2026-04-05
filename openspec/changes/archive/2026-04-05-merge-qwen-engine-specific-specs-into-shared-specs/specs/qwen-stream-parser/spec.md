## REMOVED Requirements

### Requirement: Qwen stream parser MUST support runtime stream parsing
**Reason**: runtime parser contract requirements belong to the shared `engine-adapter-runtime-contract` capability.
**Migration**: Read and update `engine-adapter-runtime-contract` for qwen runtime parsing requirements.

### Requirement: Qwen stream parser MUST support live session
**Reason**: live parser session requirements belong to the shared adapter runtime contract.
**Migration**: Read and update `engine-adapter-runtime-contract` for qwen live parsing and emission rules.

### Requirement: Qwen parser MUST detect auth signals
**Reason**: parser evidence and auth-signal handoff are part of shared runtime parsing and observability capabilities.
**Migration**: Read and update `engine-adapter-runtime-contract` and `interactive-run-observability` for qwen auth detection behavior.

### Requirement: Qwen adapter MUST be fully functional
**Reason**: adapter completeness is enforced by the shared runtime contract rather than a qwen-only capability.
**Migration**: Read and update `engine-adapter-runtime-contract` for adapter completeness and parser support requirements.

### Requirement: Qwen NDJSON event types
**Reason**: NDJSON semantic mapping and emission rules belong to the shared adapter/runtime observability capabilities.
**Migration**: Read and update `engine-adapter-runtime-contract` and `interactive-run-observability` for qwen event mapping requirements.

## ADDED Requirements

### Requirement: Qwen stream parser spec MUST contain at least one requirement
Qwen stream parser spec MUST contain at least one requirement to pass the OpenSpec validation

#### Scenario: merge spec change archived
**WHEN** OpenSpec Change: merge-qwen-engine-specific-specs-into-shared-specs is archived successfully
**THEN** User should delete the legacy `qwen-stream-parser` spec manually