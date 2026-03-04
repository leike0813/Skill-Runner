## MODIFIED Requirements

### Requirement: Lifecycle execution MUST release admission resources and reconcile orphan queued resumes
The system MUST release runtime admission resources on every post-acquire exit path and MUST reconcile non-runnable queued resume flows through canonical orchestration services.

#### Scenario: run_job releases slot after missing run directory early exit
- **WHEN** `run_job` acquires a concurrency slot and later discovers that `run_dir` is missing
- **THEN** it MUST release the acquired slot exactly once before returning

#### Scenario: queued resume with missing run dir fails reconciliation
- **GIVEN** a queued run has a pending resume ticket
- **AND** its run directory no longer exists
- **WHEN** recovery or observability evaluates whether it can redrive the queued resume
- **THEN** the system MUST NOT redrive the run
- **AND** MUST reconcile the run to `failed`
- **AND** MUST persist `recovery_state=failed_reconciled`

#### Scenario: queued resume with existing run dir redrives normally
- **GIVEN** a queued run has a pending resume ticket
- **AND** its run directory still exists
- **WHEN** recovery or observability redrives the queued resume
- **THEN** the system MAY schedule the resumed attempt
- **AND** MUST preserve existing resume semantics
