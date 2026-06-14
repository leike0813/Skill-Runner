## MODIFIED Requirements

### Requirement: Temporary runs follow unified cache policy

Temporary skill execution MUST follow the same execution-mode cache policy as installed skill runs, with normalized skill package hash and full input identity included in the cache key.

#### Scenario: Auto temporary run cache key includes package hash and inline input

- **WHEN** a temporary-skill run executes in `auto` mode and cache is enabled
- **THEN** cache lookup/write-back MAY occur
- **AND** the cache key includes the normalized skill package hash
- **AND** the cache key includes the inline input hash

#### Scenario: Different inline input does not hit temp cache

- **GIVEN** two temporary-skill requests upload the same skill package and same file inputs
- **AND** their inline input payloads differ
- **WHEN** the second request computes its cache key
- **THEN** it MUST NOT reuse the first request's cached run

#### Scenario: Interactive temporary run bypasses cache

- **WHEN** a temporary-skill run executes in `interactive` mode
- **THEN** the system does not read from or write to cache

## ADDED Requirements

### Requirement: Temporary skill package snapshots use sliding TTL

The system MUST cache validated temporary skill package snapshots by normalized skill package hash without registering them in persistent skill discovery.

#### Scenario: Reused temporary package refreshes TTL

- **WHEN** a temporary upload has the same normalized skill package hash as an existing cached snapshot
- **THEN** the system reuses the cached unpatched snapshot
- **AND** refreshes the package cache expiration time

#### Scenario: Expired temporary package snapshot is removed

- **WHEN** package-cache cleanup runs after a cached package has passed its expiration time
- **THEN** the system removes the cached snapshot and metadata
