## MODIFIED Requirements

### Requirement: Zotero Bridge CLI bundle MUST resolve from managed source with built-in fallback

The system SHALL resolve the Zotero Bridge CLI bundle from the managed bundle store when a valid active bundle exists, and SHALL fallback to the built-in `plugins/zotero-bridge-cli-bundle` submodule when no valid managed bundle is active. The management projection SHALL report the source and `surface.version` of the bundle that actually resolves.

#### Scenario: managed bundle is active
- **WHEN** deployment/bootstrap or management code resolves the Zotero Bridge bundle
- **AND** the managed bundle store has a valid active bundle
- **THEN** the system uses the managed bundle
- **AND** the management projection reports `source=managed` and the resolved manifest version

#### Scenario: managed state is invalid
- **WHEN** state references an invalid managed bundle
- **THEN** the system uses the built-in bundle
- **AND** the management projection reports `source=builtin` rather than trusting the stale state

#### Scenario: resolved manifest has no display version
- **WHEN** the resolved bundle is valid but has no `surface.version`
- **THEN** the management projection reports a null version
- **AND** the bundle remains usable

### Requirement: Zotero Bridge CLI bundle MUST support shared automatic and manual updates

The system SHALL expose separate check and install operations for administrators while keeping background automatic updates on the same update implementation.

#### Scenario: administrator checks for an update
- **WHEN** an authenticated administrator starts a manual check
- **THEN** the system compares the configured remote branch head with the active commit
- **AND** records `up_to_date` or `update_available`
- **AND** does not download or activate a bundle

#### Scenario: administrator installs a checked update
- **WHEN** a checked candidate still matches the configured remote branch head
- **THEN** the system downloads and validates that commit
- **AND** installs and activates it through the managed bundle path

#### Scenario: checked branch moved before install
- **WHEN** the configured branch head differs from the checked candidate
- **THEN** the install is rejected as a conflict
- **AND** no new bundle becomes active

#### Scenario: update fails
- **WHEN** download, validation, installation, or activation fails
- **THEN** the system continues using the previous active bundle or built-in fallback
- **AND** records a failed update state

#### Scenario: automatic updates are disabled
- **WHEN** the background automatic update setting is disabled
- **THEN** the background loop does not run
- **AND** authenticated manual check and install operations remain available

#### Scenario: automatic and manual updates overlap
- **WHEN** automatic and manual operations are requested concurrently
- **THEN** the system serializes them through the same update manager lock
- **AND** installing a commit that is already active succeeds idempotently

## ADDED Requirements

### Requirement: Zotero Bridge CLI bundle MUST use a canonical validated descriptor

The system SHALL normalize each supported bundle manifest into one immutable descriptor containing version, wrapper and profile paths, connection environment names, and platform binary SHA256 metadata. Validation, installation, and status projection SHALL consume that descriptor.

#### Scenario: current surface release is installed
- **WHEN** a `host-bridge.surface-release.v1` bundle is selected
- **THEN** the descriptor reads version from `surface.version`
- **AND** reads binary metadata from `releaseSet.cli.binaries`
- **AND** resolves the wrapper and profile template under `skills/zotero-bridge-cli`

#### Scenario: bundle validation fails
- **WHEN** the schema is unknown, a bundle path escapes the root, an artifact is missing, or the current platform SHA256 does not match
- **THEN** validation fails closed
- **AND** no wrapper, profile, or CLI artifact is copied

#### Scenario: plugin bootstrap fails during engine layout
- **WHEN** Zotero bundle parsing or installation fails inside `AgentCliManager.ensure_layout()`
- **THEN** the system records a structured plugin failure and logs the error
- **AND** continues preparing the other engine layouts
- **AND** direct validator and installer calls still raise the bundle error
