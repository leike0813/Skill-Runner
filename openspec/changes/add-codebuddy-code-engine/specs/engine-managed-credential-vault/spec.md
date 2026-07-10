## ADDED Requirements

### Requirement: Engine credentials MUST be stored by canonical provider

The system MUST persist CodeBuddy credentials in a service-local, versioned, provider-keyed vault and MUST prevent one provider from reading, replacing, or deleting another provider's credential.

#### Scenario: Domestic and global credentials coexist
- **WHEN** credentials are saved for codebuddy-cn and codebuddy-global
- **THEN** each provider lookup returns only its own credential and deleting either leaves the other unchanged

### Requirement: Credential persistence MUST be atomic and permission constrained

The vault parent directory MUST use owner-only access, the vault file MUST use owner-only read/write access, and updates MUST use atomic same-directory replacement.

#### Scenario: Credential is replaced
- **WHEN** a provider credential update completes
- **THEN** readers observe either the previous complete document or the new complete document and never a partial token payload

### Requirement: Public credential state MUST be redacted

API, logs, audit, bundles, probes, and ordinary database fields MUST NOT expose a raw token. Status projections MUST be limited to provider identity, missing|present|expired, update time, and advisory expiry.

#### Scenario: Management detail reads credential state
- **WHEN** a stored credential exists
- **THEN** the response reports present or advisory expired without returning the token or token-derived account secrets

### Requirement: Account replacement MUST invalidate provider session state

Replacing or deleting a provider credential MUST rotate that provider's persistent CLI session/config directory without modifying any other provider directory.

#### Scenario: Provider logs in as a different account
- **WHEN** authentication replaces the stored user ID for codebuddy-cn
- **THEN** prior domestic session state cannot resume and global state remains available
