## MODIFIED Requirements

### Requirement: Engine status cache service supports qwen

The engine status cache service SHALL handle `qwen` alongside the other registered engines.

#### Scenario: Initialize Qwen cache row

- **WHEN** the engine status cache service initializes or refreshes engine rows
- **THEN** `qwen` MUST be part of the cached engine set

#### Scenario: UI home status renders qwen stably

- **WHEN** the home page renders engine status indicators
- **THEN** it MUST render a stable `qwen` row even if Qwen is not installed
- **AND** missing Qwen version information MUST degrade to empty version / unavailable status without triggering live probe
