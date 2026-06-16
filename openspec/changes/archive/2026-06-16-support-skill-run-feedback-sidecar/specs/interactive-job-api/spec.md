## ADDED Requirements

### Requirement: Job create MUST accept skill run feedback runtime option

The job API SHALL accept `runtime_options.collect_skill_run_feedback` as an optional boolean that enables run-local skill feedback collection.

#### Scenario: feedback option omitted
- **WHEN** a client omits `runtime_options.collect_skill_run_feedback`
- **THEN** the system treats feedback collection as disabled
- **AND** existing runtime options remain unchanged

#### Scenario: feedback option enabled
- **WHEN** a client submits `runtime_options.collect_skill_run_feedback=true`
- **THEN** the system validates the value as a boolean
- **AND** the created run is eligible for feedback patch injection
- **AND** the cache key differs from otherwise identical default/false requests

#### Scenario: feedback option rejects non-boolean values
- **WHEN** a client submits a non-boolean `runtime_options.collect_skill_run_feedback`
- **THEN** the request is rejected by runtime option validation
