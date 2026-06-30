## ADDED Requirements

### Requirement: Adapter launch MUST explicitly bind run_dir semantics
Engine adapters SHALL treat `run_dir` as the canonical execution root and SHALL expose enough launch metadata or adapter-local behavior to bind the engine process to that root.

#### Scenario: Base adapter launches from run_dir
- **WHEN** an adapter starts or resumes an engine process
- **THEN** the subprocess cwd MUST be `run_dir`
- **AND** the adapter MUST build command and environment from the same `AdapterExecutionContext`
- **AND** the composed runtime config path MUST be available to the launch environment hook

#### Scenario: Engine declares run directory flag
- **WHEN** an engine profile declares a run directory CLI flag
- **THEN** that engine adapter MUST pass `run_dir` with that flag on start and resume
- **AND** the value MUST be the same `run_dir` used as subprocess cwd

### Requirement: Adapter profile MUST declare launch metadata
Adapter profiles SHALL declare launch metadata for cwd strategy and optional config/run-dir anchors.

#### Scenario: Profile launch metadata validates
- **WHEN** an adapter profile is loaded
- **THEN** `launch.cwd_strategy` MUST be present and valid
- **AND** `launch.config_env_var` MAY be null or a valid environment variable name
- **AND** `launch.run_dir_flag` MAY be null or a non-empty CLI flag

#### Scenario: Kilo profile declares explicit anchors
- **WHEN** the Kilo adapter profile is loaded
- **THEN** it MUST declare `cwd_strategy=run_dir`
- **AND** it MUST declare `config_env_var=KILO_CONFIG`
- **AND** it MUST declare `run_dir_flag=--dir`
