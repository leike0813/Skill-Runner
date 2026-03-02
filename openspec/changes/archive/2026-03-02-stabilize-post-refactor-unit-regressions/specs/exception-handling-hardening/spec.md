## MODIFIED Requirements

### Requirement: Broad catch MUST preserve diagnosability
Broad catch usage MUST remain tightly controlled, diagnosable, and within the approved allowlist baseline.

#### Scenario: Management routes stay within allowlist
- **WHEN** management routes handle system settings, reset actions, or engine list/detail boundaries
- **THEN** they MUST narrow `except Exception` to specific exception families or remove it entirely
- **AND** any retained best-effort boundary fallback MUST include structured logging and explicit fallback behavior
- **AND** the change MUST NOT increase global or per-file allowlist totals
