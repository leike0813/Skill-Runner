## MODIFIED Requirements

### Requirement: Upload staging MUST be request-scoped temporary storage
Orchestration MUST stage uploads in request-local temporary storage during upload handling, then decide cache hit/miss before writing uploaded run inputs to the run directory.

#### Scenario: cache hit discards temporary staging
- **WHEN** upload is processed and the v2 cache key hits
- **THEN** system MUST bind cached run
- **AND** system MUST discard temporary staging without creating run uploads directory

#### Scenario: cache miss promotes staging to run directory
- **WHEN** upload is processed and the v2 cache key misses
- **THEN** system MUST create run directory
- **AND** system MUST promote staged uploads into run directory

### Requirement: Run cache key MUST use normalized skill package identity
Orchestration MUST compute run cache keys from normalized skill package identity and complete input identity.

#### Scenario: installed and temp routes share cache when package and inputs match
- **GIVEN** an installed skill and a temporary uploaded skill have the same normalized skill package hash
- **AND** engine, parameters, options, file inputs, and inline inputs are identical
- **WHEN** an auto run computes the cache key
- **THEN** both routes compute the same v2 cache key
