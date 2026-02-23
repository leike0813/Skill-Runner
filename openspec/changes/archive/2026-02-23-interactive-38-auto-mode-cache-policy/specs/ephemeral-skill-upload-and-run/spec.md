## MODIFIED Requirements

### Requirement: Temporary run cache policy MUST be execution-mode aware
Temporary skill execution MUST apply cache policy by execution mode:
- `auto`: MAY perform cache lookup and cache write-back (unless explicitly disabled by `no_cache`)
- `interactive`: MUST bypass cache lookup and cache write-back

#### Scenario: Temporary auto run uses cache
- **WHEN** a temporary-skill run is submitted with `execution_mode=auto`
- **AND** `runtime_options.no_cache` is not `true`
- **THEN** the system performs cache lookup before execution
- **AND** successful terminal output may be written back to cache

#### Scenario: Temporary interactive run bypasses cache
- **WHEN** a temporary-skill run is submitted with `execution_mode=interactive`
- **THEN** the system executes without reading or writing cache entries

#### Scenario: Temporary auto run with explicit no_cache
- **WHEN** a temporary-skill run is submitted with `execution_mode=auto`
- **AND** `runtime_options.no_cache=true`
- **THEN** the system executes without reading or writing cache entries

### Requirement: Temporary auto cache key MUST include uploaded skill package hash
For temporary skill runs in `auto` mode, cache key composition MUST include uploaded skill package archive hash in addition to the normal request factors (inline input, file input, parameters, and engine/runtime options).

#### Scenario: Same request inputs but different temporary package archives
- **WHEN** two temporary auto runs have identical inline/file/parameter/options payloads
- **AND** uploaded skill package archives are different
- **THEN** the two runs produce different cache keys
- **AND** cache entries must not be cross-hit between the two packages

#### Scenario: Identical temporary package archive can reuse cache
- **WHEN** two temporary auto runs have identical inline/file/parameter/options payloads
- **AND** uploaded skill package archive bytes are identical
- **THEN** the two runs produce the same cache key
- **AND** the second run may hit the existing cache entry

### Requirement: Temporary cache storage MUST be isolated from regular cache storage
Temporary skill cache entries MUST be stored in a dedicated cache table/store that is independent from regular run cache entries.

#### Scenario: Same cache key string across regular and temporary paths
- **WHEN** a regular auto run and a temporary auto run produce identical cache key strings
- **THEN** each run reads/writes only within its own cache storage namespace
- **AND** temporary cache lookup MUST NOT return regular cache entries
- **AND** regular cache lookup MUST NOT return temporary cache entries
