## ADDED Requirements

### Requirement: RASP auth diagnostics MUST include structured auth_signal payload
`diagnostic.warning` events for auth-signal matches MUST carry a structured `data.auth_signal` object.

#### Scenario: high-confidence auth signal diagnostic payload
- **GIVEN** backend records a high-confidence auth signal
- **WHEN** writing RASP `diagnostic.warning`
- **THEN** `data.code` MUST be `AUTH_SIGNAL_MATCHED_HIGH`
- **AND** `data.auth_signal.confidence` MUST be `high`
- **AND** `data.auth_signal.matched_pattern_id` MUST be present.

#### Scenario: low-confidence auth signal diagnostic payload
- **GIVEN** backend records a low-confidence auth signal
- **WHEN** writing RASP `diagnostic.warning`
- **THEN** `data.code` MUST be `AUTH_SIGNAL_MATCHED_LOW`
- **AND** `data.auth_signal.confidence` MUST be `low`.
