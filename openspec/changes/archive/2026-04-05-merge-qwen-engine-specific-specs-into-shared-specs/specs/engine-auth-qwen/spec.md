## REMOVED Requirements

### Requirement: Qwen authentication providers MUST be explicit
**Reason**: Qwen provider-aware auth policy now belongs to the shared `engine-auth-strategy-policy` capability instead of a standalone qwen capability.
**Migration**: Read and update `engine-auth-strategy-policy` for explicit qwen provider declarations and method/transport matrix changes.

### Requirement: Qwen OAuth MUST use device-authorization semantics in oauth_proxy
**Reason**: oauth_proxy challenge and completion semantics are part of the shared auth session observability contract.
**Migration**: Read and update `engine-auth-observability` for qwen oauth_proxy session semantics.

### Requirement: Coding Plan providers MUST configure API-key-backed settings
**Reason**: Coding Plan write-back semantics are part of the shared auth observability and management/UI contract.
**Migration**: Read and update `engine-auth-observability`, `management-api-surface`, and `ui-engine-management` for qwen Coding Plan behavior.

### Requirement: Qwen credentials import MUST be limited to qwen-oauth in this phase
**Reason**: provider-specific import exposure is already governed by shared provider-aware management and UI capabilities.
**Migration**: Read and update `management-api-surface` and `ui-engine-management` for qwen import visibility and validation rules.

### Requirement: Qwen auth strategy configuration
**Reason**: auth strategy configuration is part of the shared strategy policy contract, not a qwen-only capability.
**Migration**: Read and update `engine-auth-strategy-policy` for qwen transport and method policy changes.

## ADDED Requirements

### Requirement: Qwen authentication spec MUST contain at least one requirement
Qwen authentication spec MUST contain at least one requirement to pass the OpenSpec validation

#### Scenario: merge spec change archived
**WHEN** OpenSpec Change: merge-qwen-engine-specific-specs-into-shared-specs is archived successfully
**THEN** User should delete the legacy `engine-auth-qwen` spec manually