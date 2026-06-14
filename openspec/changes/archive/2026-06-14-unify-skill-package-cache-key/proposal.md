## Why

Current `temp_upload` cache keys can ignore inline input and route through a separate temp cache namespace, allowing different skill requests to reuse an unrelated cached run. Installed and temporary skills also use different package identity signals, preventing valid cache sharing when the effective skill package and inputs are identical.

## What Changes

- Introduce a normalized skill package hash derived from validated skill file contents.
- Use a v2 run cache key that includes `skill_package_hash` and inline input for both installed and temporary skill routes.
- Add a 30-day sliding-TTL cache for validated temporary skill package snapshots.
- Unify installed and temporary run cache lookup/write-back through `cache_entries`.
- Keep external Jobs API request/response shapes unchanged.

## Capabilities

### New Capabilities
- `n/a`

### Modified Capabilities
- `ephemeral-skill-upload-and-run`: Temporary uploads use normalized skill package identity, include inline input in cache keys, and reuse cached package snapshots.
- `job-orchestrator-modularization`: Upload cache behavior uses a unified run cache namespace and v2 cache keys.
- `run-store-modularization`: Cache persistence no longer isolates regular and temp-upload cache hits.
- `skill-package-install`: Installed skill package identity is refreshed after install/update and on startup.

## Impact

- Affects cache key construction, run cache persistence, temporary package validation/materialization, startup lifecycle, cleanup, and related tests.
- Adds internal SQLite columns/tables for skill package identity and temporary package cache metadata.
- Existing v1 cache entries are not migrated; future cache entries use v2 keys.
