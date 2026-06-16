## MODIFIED Requirements

### Requirement: Codex compatibility translation MUST support discriminated object-union final schemas

When the canonical final schema is an object schema containing `oneOf` or `anyOf` object branches, the Codex compatibility pipeline MUST derive a flat object transport schema from that union without changing the canonical schema.

#### Scenario: Object-union final schema becomes flat Codex transport
- **GIVEN** the canonical final schema has `type=object`
- **AND** it contains `oneOf` or `anyOf` object branches
- **AND** the branches share a discriminator field with distinct `const` values
- **WHEN** Codex compatibility artifacts are materialized
- **THEN** the effective Codex schema is a single object schema
- **AND** it does not contain top-level `oneOf`, `anyOf`, or `allOf`
- **AND** it contains the merged branch fields
- **AND** branch-inactive fields are nullable placeholders
- **AND** the discriminator field exposes the allowed branch values

#### Scenario: Interactive state union remains distinct from business object union
- **GIVEN** the canonical schema contains an outer final/pending union using `__SKILL_DONE__`
- **AND** the final branch contains a business object union
- **WHEN** Codex compatibility artifacts are materialized
- **THEN** the pipeline treats the outer union as the execution state union
- **AND** it treats the final branch union as the business output union

### Requirement: Codex compatibility payloads MUST canonicalize back to the selected object-union branch

Codex flat transport payloads for object-union final schemas MUST be projected back to the branch selected by the discriminator before orchestration consumes them.

#### Scenario: Final payload selects a business branch
- **GIVEN** a Codex flat final payload contains a discriminator value
- **AND** that value matches one canonical object-union branch
- **WHEN** the payload is canonicalized
- **THEN** runtime returns the canonical final payload for that branch
- **AND** it strips fields that only belong to inactive branches
- **AND** it preserves `__SKILL_DONE__=true`

#### Scenario: Ambiguous object union is not guessed
- **GIVEN** an object-union schema has no stable distinct `const` discriminator
- **WHEN** Codex payload canonicalization cannot select a branch
- **THEN** runtime MUST NOT silently guess a branch
- **AND** downstream canonical validation remains responsible for reporting the contract violation
