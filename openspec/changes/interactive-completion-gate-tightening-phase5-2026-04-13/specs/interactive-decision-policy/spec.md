## ADDED Requirements

### Requirement: Interactive Completion Gate Keeps Stable Compatibility Codes

Phase 5 MUST preserve the existing warning and diagnostic codes for
compatibility completion and invalid structured output handling.

#### Scenario: soft completion keeps the established warning code
- **WHEN** an interactive attempt completes through soft completion
- **THEN** runtime MUST continue to emit
  `INTERACTIVE_COMPLETED_WITHOUT_DONE_MARKER`

#### Scenario: permissive schema keeps the existing compatibility warning
- **WHEN** an interactive attempt completes through soft completion
- **AND** the output schema is too permissive
- **THEN** runtime MUST continue to emit
  `INTERACTIVE_SOFT_COMPLETION_SCHEMA_TOO_PERMISSIVE`

#### Scenario: invalid structured output keeps the existing waiting warning
- **WHEN** an interactive attempt produces structured output
- **AND** that output fails schema validation
- **THEN** runtime MUST continue to emit
  `INTERACTIVE_OUTPUT_EXTRACTED_BUT_SCHEMA_INVALID`

### Requirement: Explicit Branches Define The Formal Contract

Interactive decision policy MUST treat the final and pending union branches as
the formal contract even while compatibility paths remain enabled.

#### Scenario: compatibility completion is not promoted to a formal branch
- **WHEN** soft completion is used
- **THEN** runtime MAY complete the attempt
- **AND** soft completion MUST remain documented as a compatibility path rather
  than the formal output contract
