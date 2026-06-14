## 1. OpenSpec and docs

- [x] 1.1 Add delta specs for unified package identity, temp package TTL cache, and shared run cache namespace.
- [x] 1.2 Update execution flow documentation for cache key v2 and temp package cache behavior.

## 2. Identity and persistence

- [x] 2.1 Add normalized skill package hash computation.
- [x] 2.2 Add run-store schema and methods for `requests.skill_package_hash`, installed package identities, and temporary package cache metadata.
- [x] 2.3 Add startup/install hooks to refresh installed/builtin skill package hashes.

## 3. Temp package cache and materialization

- [x] 3.1 Add validated temp package snapshot cache with 30-day sliding TTL.
- [x] 3.2 Materialize temp runs from cached unpatched snapshots instead of deleted inspection temp dirs.
- [x] 3.3 Add cleanup for expired temporary package snapshots.

## 4. Run cache behavior

- [x] 4.1 Upgrade cache key payload to v2 with `skill_package_hash`.
- [x] 4.2 Include temp route inline input in cache keys.
- [x] 4.3 Read/write all new run cache entries through `cache_entries`.

## 5. Tests

- [x] 5.1 Cover normalized package hash and v2 cache key behavior.
- [x] 5.2 Cover temp upload cache miss for different inline input and shared installed/temp cache hit.
- [x] 5.3 Cover temp package snapshot TTL reuse and cleanup.
