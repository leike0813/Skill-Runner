## REMOVED Requirements

### Requirement: Qwen UI shell MUST enforce security restrictions
**Reason**: inline terminal / UI shell session restrictions belong to the shared `ui-engine-inline-terminal` capability.
**Migration**: Read and update `ui-engine-inline-terminal` for engine-declared session security policy requirements.

### Requirement: Qwen config schema MUST validate permissions and tools
**Reason**: session-local UI shell config assets and validation now belong to the shared adapter/runtime contract and config layering capabilities.
**Migration**: Read and update `engine-adapter-runtime-contract` and `engine-runtime-config-layering` for UI shell config schema and layering requirements.

### Requirement: Qwen adapter profile MUST declare UI shell config assets
**Reason**: adapter profile asset declaration is part of the shared runtime contract, not a qwen-only capability.
**Migration**: Read and update `engine-adapter-runtime-contract` for UI shell config asset declaration requirements.

## ADDED Requirements

### Requirement: Qwen UI shell security spec MUST contain at least one requirement
Qwen UI shell security spec MUST contain at least one requirement to pass the OpenSpec validation

#### Scenario: merge spec change archived
**WHEN** OpenSpec Change: merge-qwen-engine-specific-specs-into-shared-specs is archived successfully
**THEN** User should delete the legacy `qwen-ui-shell-security` spec manually