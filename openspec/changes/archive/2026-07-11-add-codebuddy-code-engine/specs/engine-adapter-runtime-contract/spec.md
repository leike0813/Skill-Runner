## ADDED Requirements

### Requirement: CodeBuddy adapter MUST enforce provider-scoped execution

The adapter MUST require codebuddy-cn or codebuddy-global, use the matching managed credential and persistent config directory, and start every attempt as a fresh subprocess in the run directory.

#### Scenario: Exact session resume is requested
- **WHEN** an interactive reply resumes a CodeBuddy session
- **THEN** the adapter emits -r with the exact session ID and original provider directory and does not emit --continue

### Requirement: CodeBuddy credential preflight MUST fail before process launch

The shared adapter contract MUST represent engine authentication preflight failures with a RuntimeAuthSignal. CodeBuddy missing or expired credentials MUST return AUTH_REQUIRED with empty redacted stdout and stderr without starting the task CLI.

#### Scenario: Managed credential is missing
- **WHEN** command parsing succeeds but the selected provider credential is missing
- **THEN** execution returns a high-confidence CODEBUDDY_CREDENTIAL_MISSING auth signal and spawns no task process

#### Scenario: Managed credential is expired
- **WHEN** command parsing succeeds but the selected provider credential is expired
- **THEN** execution returns a high-confidence CODEBUDDY_CREDENTIAL_EXPIRED auth signal and spawns no task process

### Requirement: CodeBuddy completion MUST depend on a terminal result event

A CodeBuddy attempt MUST complete only after a success result with is_error=false; an error result, is_error=true, or missing terminal result MUST fail regardless of process exit code.

#### Scenario: CLI emits an auth error and exits zero
- **WHEN** a terminal error result is followed by process exit code 0
- **THEN** the runtime marks the turn failed and preserves the high-confidence auth signal

#### Scenario: Output redaction fails before a terminal result can be captured
- **WHEN** the process output capture layer terminates CodeBuddy with `OUTPUT_REDACTION_FAILED`
- **THEN** the runtime reports that infrastructure failure instead of synthesizing a missing-terminal failure
- **AND** no unredacted output is persisted or published

### Requirement: CodeBuddy stream JSON semantics MUST be published incrementally

The live parser MUST publish each complete CodeBuddy stream JSON record while the process is still running. Run handles, reasoning, tool activity, and assistant text MUST NOT wait for process exit; terminal success still requires a valid result record.

#### Scenario: A thinking record arrives before process exit
- **WHEN** the live parser receives a complete thinking record
- **THEN** it immediately emits the corresponding reasoning event
- **AND** finishing the process does not emit that reasoning event again

#### Scenario: A complete redacted physical record is available
- **WHEN** output chunks complete a physical record without exposing a secret
- **THEN** the redactor releases that record immediately instead of retaining a fixed multi-kilobyte tail

### Requirement: CodeBuddy structured output MUST use the shared result pipeline

The adapter MUST pass an inline JSON schema through --json-schema and forward result.structured_output into the shared structured-output validation and persistence path.

#### Scenario: Structured output is present
- **WHEN** the terminal result contains structured_output
- **THEN** the job result exposes the validated structure without deriving it from assistant text
