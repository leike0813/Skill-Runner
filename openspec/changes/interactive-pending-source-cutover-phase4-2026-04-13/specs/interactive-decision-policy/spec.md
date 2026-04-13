## ADDED Requirements

### Requirement: Phase 4 Preserves Soft Completion

Phase 4 MUST NOT tighten final completion semantics.

#### Scenario: Soft completion remains a legacy completion path
- **WHEN** an interactive attempt produces schema-valid business output without
  an explicit done marker
- **THEN** runtime MAY continue to treat that attempt as a soft completion
- **AND** this phase MUST NOT convert that path into waiting-only behavior
