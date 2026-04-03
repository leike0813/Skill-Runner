## MODIFIED Requirements

### Requirement: Managed engine install and upgrade support Claude

The engine management domain SHALL support managed install and upgrade for `claude`.

#### Scenario: Ensure Claude

- **WHEN** bootstrap or explicit ensure targets `claude`
- **THEN** the manager MUST install `@anthropic-ai/claude-code`
- **AND** it MUST detect the executable via `claude`, `claude.cmd`, or `claude.exe`

#### Scenario: Single-engine UI action on Claude

- **WHEN** the management UI triggers a single-engine action for `claude`
- **THEN** the backend MUST perform `install` if Claude is absent
- **AND** it MUST perform `upgrade` if Claude is already present
