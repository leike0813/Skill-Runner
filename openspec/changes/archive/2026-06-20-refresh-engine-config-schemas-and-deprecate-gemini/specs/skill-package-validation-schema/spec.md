## MODIFIED Requirements

### Requirement: runner manifest MUST validate engine declarations against active engine enum

Skill package engine declarations MUST use active supported engines only.

#### Scenario: Gemini engine declaration rejected
- **WHEN** a skill package declares `engines=["gemini"]` or `unsupported_engines=["gemini"]`
- **THEN** package validation MUST reject the manifest as unsupported

#### Scenario: omitted engines default excludes Gemini
- **WHEN** a skill package omits `engines`
- **THEN** computed `effective_engines` MUST include active engines only
- **AND** MUST NOT include `gemini`
