## ADDED Requirements

### Requirement: Temp Skill Is Materialized Into Run-Local Snapshot

Temp skill runs MUST materialize the uploaded skill into the run directory before dispatch begins.

#### Scenario: Temp run create
- WHEN a temp skill run is created
- THEN the uploaded skill is unpacked and patched into `data/runs/<run_id>/.<engine>/skills/<skill_id>/`
- AND later attempts and resumed attempts load from that run-local snapshot

### Requirement: Temp Staging Is Import-Only

Temp staging directories MUST NOT be required for resumed attempts.

#### Scenario: Resume after import cleanup
- GIVEN a temp skill run has already materialized a run-local snapshot
- WHEN a resumed attempt starts
- THEN the skill loads from the run-local snapshot
- AND temp staging may already be absent
