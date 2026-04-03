## MODIFIED Requirements

### Requirement: Engine Runtime Preparation

Engine runtime preparation MUST perform engine-agnostic workspace setup before engine-specific execution begins.

#### Scenario: Run folder is git-initialized before trust registration

- **WHEN** a managed run/session directory enters trust lifecycle for API runs, auth sessions, harness runs, or UI shell sessions
- **THEN** the system ensures the directory is itself a git repository root before registering trust
- **AND** the operation is idempotent when `.git/` already exists

#### Scenario: Claude trust payload marks trust dialog accepted

- **WHEN** a Claude run/session folder is registered
- **THEN** the persisted Claude project entry includes the acceptance flag required to suppress the trust dialog for that run/session path
