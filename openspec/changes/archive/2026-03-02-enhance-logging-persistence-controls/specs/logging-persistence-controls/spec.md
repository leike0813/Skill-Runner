## ADDED Requirements

### Requirement: Global app logs MUST persist to disk with configurable path and policy
The system MUST persist application logs to a disk file under a configurable directory and filename policy.

#### Scenario: Startup initializes global logging
- **WHEN** the service starts and calls `setup_logging()`
- **THEN** logs are emitted to both stream and file handlers
- **AND** file path resolution follows configured logging directory and basename inputs

### Requirement: Global app logs MUST rotate daily with retention controls
The system MUST rotate global log files on a daily schedule and retain files according to configured retention days.

#### Scenario: Daily rollover boundary is reached
- **WHEN** log writes cross the daily rollover boundary
- **THEN** the active log file is rotated by timed policy
- **AND** the number of retained rotated files respects retention configuration

### Requirement: Global app logs directory MUST enforce total quota with oldest-first eviction
The system MUST enforce a max-bytes quota for the global log directory and MUST evict oldest archived logs first when over limit.

#### Scenario: Log directory exceeds quota
- **WHEN** total bytes of active plus archived files for the global app log exceed configured quota
- **THEN** oldest archived files are removed first until under quota or no archive remains
- **AND** the active log file is never deleted by quota cleanup

### Requirement: Logging output MUST support text default and optional JSON format
The system MUST provide text format by default and optional JSON format via configuration.

#### Scenario: JSON format is enabled
- **WHEN** logging format configuration is set to `json`
- **THEN** each emitted record contains at least `timestamp`, `level`, `logger`, and `message` fields
- **AND** logging behavior remains backward compatible in text mode by default

### Requirement: Configuration MUST be driven by core_config with environment overrides
The system MUST source logging defaults from `core_config` and allow environment variables to override key settings.

#### Scenario: Environment override is provided
- **WHEN** environment variables for log level/dir/format/retention/quota are set
- **THEN** those values override `core_config` defaults at runtime
- **AND** unset values continue to use `core_config` defaults

### Requirement: Logging setup MUST degrade safely on file sink failures
The system MUST continue serving with stream logging if file handler initialization fails.

#### Scenario: Log file handler cannot be initialized
- **WHEN** the file sink raises an OS/file-system error during setup
- **THEN** stream logging remains active
- **AND** a warning is emitted with diagnostic fields including component/action/error_type/fallback

### Requirement: CI/tests MUST guard against regressions in logging behavior
The system MUST include tests that verify setup idempotency, format switch behavior, and quota cleanup semantics.

#### Scenario: Logging behavior regression introduced
- **WHEN** tests execute logging unit suites
- **THEN** regressions in handler duplication, JSON payload shape, or quota cleanup are detected and fail CI

