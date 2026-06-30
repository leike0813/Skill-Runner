## ADDED Requirements

### Requirement: Kilo bootstrap configuration MUST be written to managed agent home

The bootstrap system SHALL write Kilo baseline config to the managed agent home.

#### Scenario: Write Kilo bootstrap config

- **WHEN** the system bootstraps Kilo
- **THEN** it MUST create the configured Kilo directories
- **AND** it MUST write bootstrap config to the profile-declared Kilo target path

### Requirement: Kilo run folder MUST include workspace and skills directories

Kilo run materialization SHALL create the profile-declared workspace and skills directories.

#### Scenario: Prepare Kilo run folder

- **WHEN** a Kilo run folder is prepared
- **THEN** `.kilo/` MUST exist
- **AND** `.kilo/skills/` MUST exist
