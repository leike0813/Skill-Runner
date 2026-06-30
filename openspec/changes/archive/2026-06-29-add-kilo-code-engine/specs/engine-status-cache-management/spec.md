## ADDED Requirements

### Requirement: Engine status cache service supports kilo

The engine status cache service SHALL handle `kilo` alongside other active engines.

#### Scenario: Initialize Kilo cache row

- **WHEN** the engine status cache initializes or refreshes engine rows
- **THEN** `kilo` MUST be part of the cached engine set

#### Scenario: UI renders Kilo status stably

- **WHEN** the engine management UI renders status
- **THEN** it MUST render a stable Kilo row even if Kilo is not installed
- **AND** missing version information MUST not trigger a live probe on read paths
