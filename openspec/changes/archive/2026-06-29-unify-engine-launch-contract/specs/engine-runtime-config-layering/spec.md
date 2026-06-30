## ADDED Requirements

### Requirement: Runtime config path MUST be available to launch env
Runtime config composition SHALL return a concrete config path before engine launch, and the launch environment hook SHALL receive that path.

#### Scenario: Engine declares config env var
- **GIVEN** an engine profile declares a non-null `launch.config_env_var`
- **WHEN** runtime config composition succeeds
- **THEN** the engine launch environment MUST set that env var to the composed config path
- **AND** the engine process MUST NOT be launched if config composition fails

#### Scenario: Engine does not declare config env var
- **GIVEN** an engine profile declares `launch.config_env_var=null`
- **WHEN** runtime config composition succeeds
- **THEN** launch environment behavior MUST remain compatible with existing engine-specific env behavior

### Requirement: Kilo runtime config MUST be explicitly anchored
Kilo runtime launch SHALL pass the composed run-local config file through `KILO_CONFIG`.

#### Scenario: Kilo config env
- **WHEN** Kilo prepares a run with config path `<run_dir>/.kilo/kilo.jsonc`
- **THEN** the launch environment MUST include `KILO_CONFIG=<run_dir>/.kilo/kilo.jsonc`
- **AND** the value MUST point to the composed run-local config file for that attempt
