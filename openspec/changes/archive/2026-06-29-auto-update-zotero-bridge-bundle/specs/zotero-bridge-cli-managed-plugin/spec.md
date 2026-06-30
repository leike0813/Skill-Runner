## MODIFIED Requirements

### Requirement: Zotero Bridge CLI bundle MUST resolve from managed source with built-in fallback

The system SHALL resolve the Zotero Bridge CLI bundle from the managed bundle store when a valid active bundle exists, and SHALL fallback to the built-in `plugins/zotero-bridge-cli-bundle` submodule when no valid managed bundle is active.

#### Scenario: managed bundle is active
- **WHEN** deployment/bootstrap code needs the Zotero Bridge bundle
- **AND** the managed bundle store has a valid active bundle
- **THEN** the system reads `manifest.json`, `bin/`, `skills/zotero-bridge-cli/`, and `assets/profile.template.json` from the managed bundle

#### Scenario: no managed bundle is active
- **WHEN** deployment/bootstrap code needs the Zotero Bridge bundle
- **AND** the managed bundle store has no valid active bundle
- **THEN** the system reads the built-in bundle from `plugins/zotero-bridge-cli-bundle`

### Requirement: Zotero Bridge CLI bundle MUST auto-update from configured Git branch

The system SHALL run a non-blocking background updater that tracks the configured Git repository and branch for the Zotero Bridge CLI bundle.

#### Scenario: new upstream commit is available
- **WHEN** the updater detects a remote branch commit different from the active managed commit
- **THEN** it fetches the branch content into staging
- **AND** validates bundle structure and the current platform binary SHA256
- **AND** atomically activates the new bundle before reinstalling the managed CLI and wrapper skill

#### Scenario: update fails
- **WHEN** the updater cannot fetch or validate the new bundle
- **THEN** the service continues using the previous active bundle
- **AND** if no active managed bundle exists, the service continues using the built-in submodule fallback
- **AND** the failure is recorded in the bundle update state
