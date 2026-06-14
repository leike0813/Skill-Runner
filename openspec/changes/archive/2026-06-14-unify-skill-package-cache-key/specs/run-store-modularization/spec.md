## MODIFIED Requirements

### Requirement: Dedicated persistence sub-stores MUST preserve request, run, and cache behavior
The system MUST provide dedicated internal stores for request/run registry and cache persistence while supporting unified cache lookup for installed and temporary skill sources.

#### Scenario: Regular and temp cache share namespace
- **WHEN** installed and temp-upload routes compute the same v2 cache key
- **THEN** the system MUST use the same `cache_entries` backing store
- **AND** `get_cached_run_for_source` MUST return the same cached run regardless of source
