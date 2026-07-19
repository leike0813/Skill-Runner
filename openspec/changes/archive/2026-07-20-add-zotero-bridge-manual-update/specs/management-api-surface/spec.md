## ADDED Requirements

### Requirement: Management API MUST expose protected Zotero Bridge CLI plugin update operations

The system MUST expose stable management endpoints for reading Zotero Bridge CLI plugin status, checking for an update, and installing the last checked update. All endpoints MUST use the UI Basic Auth protection boundary.

#### Scenario: read local plugin status
- **WHEN** an authenticated client calls `GET /v1/management/system/plugins/zotero-bridge-cli`
- **THEN** the response includes the stable plugin identity, resolved version and source, active commit, update status, candidate commit, timestamps, and sanitized error fields
- **AND** does not expose bundle or cache paths
- **AND** does not access the network

#### Scenario: check for an update
- **WHEN** an authenticated client calls `POST /v1/management/system/plugins/zotero-bridge-cli/check`
- **THEN** the service checks the configured remote branch
- **AND** returns the updated stable status projection

#### Scenario: install a checked update
- **WHEN** an authenticated client calls `POST /v1/management/system/plugins/zotero-bridge-cli/install`
- **AND** the checked candidate is still current
- **THEN** the service installs it and returns the updated stable status projection

#### Scenario: no installable candidate exists
- **WHEN** the install endpoint is called without a current checked candidate
- **THEN** the system returns `409`

#### Scenario: unauthenticated update request
- **WHEN** UI Basic Auth is enabled and a client omits valid credentials
- **THEN** each plugin management endpoint returns `401`
- **AND** no check or installation work begins
