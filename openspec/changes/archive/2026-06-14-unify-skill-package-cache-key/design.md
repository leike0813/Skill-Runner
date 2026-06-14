## Context

Temporary skill execution currently computes cache keys from uploaded input files and the raw temporary package hash, but the `temp_upload` path explicitly clears the inline input hash. For skills such as `tag-regulator`, the meaningful business input is inline metadata, so distinct requests can collide. The runtime also stores temp cache entries separately from installed cache entries, which prevents deliberate sharing when an installed skill and a temporary package have identical contents.

## Decisions

### Decision 1: Normalized package content hash is the skill identity

Compute `skill_package_hash` by walking the validated skill directory, sorting files by relative path, and hashing each relative path plus file content hash. This ignores zip ordering, compression, and mtime metadata. Git metadata is excluded so temporary packages align with installed packages after install-time `.git` stripping.

### Decision 2: Cache key v2 uses package identity plus full input identity

Run cache keys include `cache_key_version=2`, `skill_id`, `engine`, `skill_package_hash`, `parameter`, `engine_options`, `input_manifest_hash`, and `inline_input_hash`. `skill_fingerprint` remains stored for compatibility but is no longer part of the v2 key.

### Decision 3: Temporary packages cache validated snapshots

Temporary uploads are extracted and validated before hashing. The system stores an unpatched snapshot under `TEMP_SKILL_PACKAGE_CACHE_DIR/<skill_package_hash>/snapshot` and records metadata in `runs.db`. A cache hit refreshes `last_accessed_at` and `expires_at`; the default TTL is 30 days.

### Decision 4: Run cache namespace is unified

Both installed and temporary successful auto runs write to `cache_entries`, and cache lookup ignores `skill_source`. `temp_cache_entries` remains in schema and cleanup for legacy compatibility but new code does not use it.

## Migration

- Add columns/tables with additive SQLite migrations.
- Existing run cache rows are not migrated; v2 cache keys naturally avoid accidental hits against v1 keys.
- Existing requests may have null `skill_package_hash`; new requests populate it during cache key computation.

## Risks

- Startup hash refresh scans all installed/builtin skill directories; hashing is bounded by package size and can be best-effort with warning logs.
- Cached temporary snapshots must remain unpatched; run materialization must copy then patch into run-local engine directories.
