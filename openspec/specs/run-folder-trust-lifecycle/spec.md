# run-folder-trust-lifecycle Specification

## Purpose
TBD - created by archiving change run-folder-trust-management. Update Purpose after archive.
## Requirements
### Requirement: Register and remove run folder trust for Codex and Gemini
The system MUST register trust for the current `run_dir` before invoking Codex or Gemini, and MUST remove the same trust record after execution completes.

#### Scenario: Codex run registers trust before execution
- **WHEN** a job is scheduled with engine `codex` and a resolved run directory
- **THEN** the system writes `projects."<run_dir>".trust_level = "trusted"` to Codex global config before starting Codex CLI

#### Scenario: Gemini run registers trust before execution
- **WHEN** a job is scheduled with engine `gemini` and a resolved run directory
- **THEN** the system writes `"<run_dir>": "TRUST_FOLDER"` into `~/.gemini/trustedFolders.json` before starting Gemini CLI

#### Scenario: Trust is removed after successful execution
- **WHEN** Codex or Gemini execution finishes successfully
- **THEN** the system removes the run directory trust entry from the corresponding global config

#### Scenario: Trust is removed after failed execution
- **WHEN** Codex or Gemini execution exits with error or raises exception
- **THEN** the system still attempts trust-entry removal in a finally-path cleanup

### Requirement: iFlow behavior remains unchanged
The system MUST NOT apply unsupported trust-folder mutations for iFlow.

#### Scenario: iFlow run does not mutate trust config
- **WHEN** a job is scheduled with engine `iflow`
- **THEN** no Codex/Gemini trust config mutations are performed for that run

### Requirement: Trust mutations must be concurrency-safe
The system MUST update global trust configuration files using atomic, lock-protected operations to avoid corruption under concurrent runs.

#### Scenario: Concurrent Codex trust updates
- **WHEN** multiple Codex jobs add/remove trust records concurrently
- **THEN** resulting TOML remains parseable and contains only expected trust entries

#### Scenario: Concurrent Gemini trust updates
- **WHEN** multiple Gemini jobs add/remove trust records concurrently
- **THEN** resulting JSON remains valid object format with expected key-value entries

### Requirement: Cleanup failure handling
The system MUST not change job terminal status because of trust cleanup failure, and MUST log cleanup failure for later remediation.

#### Scenario: Cleanup failure after run completion
- **WHEN** trust-entry deletion fails due to I/O or parse error
- **THEN** the job status remains based on execution result, and a warning/error log is emitted for cleanup retry tooling

