## MODIFIED Requirements

### Requirement: Claude runtime command and config responsibilities are separated

The Claude adapter runtime contract SHALL keep protocol-level command defaults separate from policy-level configuration.

#### Scenario: headless Claude run uses thin command defaults

- **WHEN** the system builds a Claude `start` or `resume` command for headless execution
- **THEN** it MUST only include the protocol defaults required for headless execution
- **AND** it MUST NOT pass model selection, settings path, permission mode, or provider credentials as CLI flags

#### Scenario: Claude runtime settings hold policy and model injection

- **WHEN** the system prepares Claude runtime settings for a headless run or harness execution
- **THEN** it MUST write model/provider configuration into `run_dir/.claude/settings.json`
- **AND** it MUST enforce sandbox and permission policy through settings rather than command flags

#### Scenario: Claude ui shell uses a separate security posture

- **WHEN** the system starts a Claude `ui_shell` session
- **THEN** it MUST use a dedicated session security strategy
- **AND** it MUST NOT reuse the headless `bypassPermissions` policy for that session

### Requirement: Claude settings validation uses real JSON Schema semantics

The configuration validation path SHALL validate Claude settings with the vendored Claude JSON Schema.

#### Scenario: Claude settings include env and sandbox sections

- **WHEN** the generated Claude settings include `env`, `permissions`, `sandbox`, or `includeGitInstructions`
- **THEN** the validator MUST recognize those keys as valid schema-backed settings
- **AND** it MUST NOT emit unknown-key warnings for them
