## ADDED Requirements

### Requirement: Kilo CLI MUST be managed installable

The engine management layer SHALL support managed installation of `@kilocode/cli`.

#### Scenario: Install Kilo Code

- **WHEN** the user requests install or upgrade for `kilo`
- **THEN** the system MUST run npm install for the package declared in Kilo adapter profile
- **AND** it MUST verify one of the profile-declared Kilo binary candidates is available

### Requirement: Kilo CLI binary detection MUST support aliases

Kilo binary detection SHALL support both `kilo` and `kilocode` aliases across supported platforms.

#### Scenario: Detect Kilo CLI

- **WHEN** the system resolves the Kilo command
- **THEN** it MUST check profile-declared candidates including `kilo` and `kilocode`
