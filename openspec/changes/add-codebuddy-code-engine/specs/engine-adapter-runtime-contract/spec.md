## ADDED Requirements

### Requirement: CodeBuddy adapter MUST enforce provider-scoped execution

The adapter MUST require codebuddy-cn or codebuddy-global, use the matching managed credential and persistent config directory, and start every attempt as a fresh subprocess in the run directory.

#### Scenario: Exact session resume is requested
- **WHEN** an interactive reply resumes a CodeBuddy session
- **THEN** the adapter emits -r with the exact session ID and original provider directory and does not emit --continue

### Requirement: CodeBuddy completion MUST depend on a terminal result event

A CodeBuddy attempt MUST complete only after a success result with is_error=false; an error result, is_error=true, or missing terminal result MUST fail regardless of process exit code.

#### Scenario: CLI emits an auth error and exits zero
- **WHEN** a terminal error result is followed by process exit code 0
- **THEN** the runtime marks the turn failed and preserves the high-confidence auth signal

### Requirement: CodeBuddy structured output MUST use the shared result pipeline

The adapter MUST pass an inline JSON schema through --json-schema and forward result.structured_output into the shared structured-output validation and persistence path.

#### Scenario: Structured output is present
- **WHEN** the terminal result contains structured_output
- **THEN** the job result exposes the validated structure without deriving it from assistant text
