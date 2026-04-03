## MODIFIED Requirements

### Requirement: Claude runtime command and config responsibilities are separated

The Claude adapter runtime contract SHALL keep protocol-level command defaults separate from policy-level configuration.

#### Scenario: headless Claude keeps sandbox enabled with controlled fallback

- **WHEN** the system prepares Claude runtime settings for a headless run or harness execution
- **THEN** it MUST keep `sandbox.enabled = true`
- **AND** it MUST allow a controlled unsandboxed fallback for known sandbox infrastructure failures rather than hard-forcing all Bash work to remain sandboxed
- **AND** it MUST keep this policy in settings rather than command flags

#### Scenario: headless Claude preserves run-local write boundaries while allowing temporary workdir writes

- **WHEN** the system composes Claude headless sandbox filesystem policy
- **THEN** it MUST allow writes to the current run directory
- **AND** it MUST continue denying writes to managed agent home and out-of-run project roots
- **AND** it MUST additionally allow a conservative temporary write location for normal subprocess workflows

#### Scenario: Claude ui shell keeps a separate restrictive posture

- **WHEN** the system starts a Claude `ui_shell` session
- **THEN** it MUST keep the dedicated restrictive session security strategy
- **AND** it MUST NOT inherit the headless unsandboxed fallback posture

#### Scenario: headless Claude prompt restricts fallback scope

- **WHEN** the system renders the default Claude prompt for headless execution
- **THEN** it MUST instruct Claude to prefer sandboxed Bash first
- **AND** it MUST only permit unsandboxed fallback for known sandbox infrastructure failures
- **AND** it MUST forbid using that fallback for ordinary policy denials such as disallowed network access or out-of-bound writes
