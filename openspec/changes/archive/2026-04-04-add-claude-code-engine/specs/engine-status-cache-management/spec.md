## MODIFIED Requirements

### Requirement: Engine status cache covers Claude

The engine status cache SHALL include `claude` alongside the existing managed engines.

#### Scenario: Refresh engine status snapshot

- **WHEN** status cache refresh runs
- **THEN** the snapshot MUST contain an entry for `claude`
- **AND** an uninstalled Claude CLI MUST remain observable as `present=false`

### Requirement: Claude model catalog is static manifest based

Claude model discovery SHALL use the manifest/snapshot path rather than runtime probing.

#### Scenario: Load Claude models

- **WHEN** management or UI requests models for `claude`
- **THEN** the model registry MUST read Claude models from a static manifest
- **AND** it MUST not rely on runtime probe refresh
