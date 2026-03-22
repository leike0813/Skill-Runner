## MODIFIED Requirements

### Requirement: Waiting-auth transition MUST be high-confidence only
Only high-confidence auth signal MUST drive `waiting_auth` entry and terminal auth-required attribution.

Low-confidence auth signal is diagnostic-only and MUST NOT force `waiting_auth` or rewrite a terminal non-auth failure into `AUTH_REQUIRED`.

#### Scenario: High-confidence auth signal enters waiting_auth
- **GIVEN** `auth_signal.required=true` and `confidence=high`
- **AND** idle-blocking early-exit condition is satisfied (if process still blocked)
- **THEN** runtime MUST transition to `waiting_auth` flow.

#### Scenario: Low-confidence auth signal does not enter waiting_auth
- **GIVEN** `auth_signal.required=true` and `confidence=low`
- **THEN** runtime MUST keep it as diagnostic evidence only
- **AND** MUST NOT transition to `waiting_auth` based solely on that signal.

#### Scenario: Low-confidence auth signal does not rewrite terminal failure
- **GIVEN** `auth_signal.required=true` and `confidence=low`
- **AND** the process exits non-zero for a non-auth failure
- **WHEN** lifecycle normalizes the terminal result
- **THEN** terminal error code MUST NOT be `AUTH_REQUIRED`
- **AND** the low-confidence signal MUST remain available in audit diagnostics
