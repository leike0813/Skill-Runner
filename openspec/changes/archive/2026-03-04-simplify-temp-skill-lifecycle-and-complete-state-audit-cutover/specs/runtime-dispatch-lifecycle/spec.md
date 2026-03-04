## ADDED Requirements

### Requirement: Dispatch Starts Only After Run-Local Materialization

Run dispatch MUST begin only after the run-local skill snapshot exists.

#### Scenario: Temp skill dispatch
- GIVEN a temp skill upload is accepted
- WHEN the run is created
- THEN the run-local skill snapshot is materialized before `dispatch_scheduled`
