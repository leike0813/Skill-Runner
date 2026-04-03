## MODIFIED Requirements

### Requirement: Claude runtime command and config responsibilities are separated

The Claude adapter runtime contract SHALL keep protocol-level command defaults separate from policy-level configuration.

#### Scenario: bootstrap probe gates headless Claude sandbox enablement

- **WHEN** the service bootstraps Claude runtime layout
- **THEN** it MUST perform a real Claude sandbox availability probe rather than relying only on dependency presence
- **AND** it MUST persist that probe result for later headless Claude runs
- **AND** a headless Claude run MUST only keep `sandbox.enabled = true` when the bootstrap probe result is available

#### Scenario: bootstrap probe failure disables headless sandbox without blocking runs

- **WHEN** the Claude bootstrap probe reports dependency missing, timeout, namespace failure, or equivalent runtime unavailability
- **THEN** the system MUST disable Claude sandbox for later headless runs
- **AND** it MUST continue the run in fail-open mode rather than failing the run during bootstrap

#### Scenario: Claude ui shell keeps its own sandbox posture

- **WHEN** the system starts a Claude `ui_shell` session
- **THEN** it MUST keep the dedicated `ui_shell` sandbox logic
- **AND** it MUST NOT inherit the bootstrap-gated headless sandbox enablement result

#### Scenario: default Claude prompt matches bootstrap sandbox availability

- **WHEN** the system renders the default Claude prompt for headless execution
- **THEN** it MUST instruct Claude to prefer sandbox-first execution only when bootstrap probe says sandbox is available
- **AND** it MUST instruct Claude to execute Bash normally when bootstrap probe says sandbox is unavailable
