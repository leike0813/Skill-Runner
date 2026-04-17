## ADDED Requirements

### Requirement: Success-result structured output is a generic adapter capability

The runtime MUST model success-result structured output extraction as a generic adapter capability instead of a Claude-only behavior.

#### Scenario: Claude declares success-result structured output extraction
- **WHEN** the Claude adapter profile is loaded
- **THEN** it declares a structured-output success-result strategy
- **AND** parser capability truth marks Claude as supporting success-result structured output extraction

### Requirement: Accepted success source is explicit

The runtime MUST persist the accepted success source as machine-readable metadata.

#### Scenario: Structured output result is accepted
- **WHEN** an engine success result carries accepted structured output
- **THEN** convergence and outcome record `structured_output_result`
- **AND** audit and terminal/result metadata expose that accepted success source

### Requirement: Done marker is fallback-only

Done-marker handling MUST only run after explicit structured-output and repair paths are exhausted.

#### Scenario: Structured output succeeds before done marker fallback
- **WHEN** structured output is accepted
- **THEN** done-marker scanning does not affect ordinary completion precedence
- **AND** success is not attributed to `DONE_MARKER_FOUND`
