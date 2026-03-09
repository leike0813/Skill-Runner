## ADDED Requirements

### Requirement: Backend auth detection MUST use parser-signal single source
runtime auth detection MUST be parser-signal driven, with evidence declarations only from adapter profiles and common fallback patterns.

#### Scenario: runtime does not read legacy yaml rule packs
- **WHEN** backend loads auth detection declarations
- **THEN** it MUST NOT read `server/engines/auth_detection/*.yaml`
- **AND** parser MUST classify auth signal directly from declared match patterns.

#### Scenario: fallback signal is low-confidence only
- **GIVEN** engine-specific evidence is not matched
- **AND** common fallback evidence is matched
- **THEN** parser MUST emit `auth_signal.required=true` and `confidence=low`.
