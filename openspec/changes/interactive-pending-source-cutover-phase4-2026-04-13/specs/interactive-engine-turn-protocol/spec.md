## ADDED Requirements

### Requirement: Legacy Ask-User Markup Does Not Populate Waiting Payloads

Interactive engine turn processing MUST reject deprecated ask-user wrappers as a
data source for waiting payload enrichment.

#### Scenario: Deprecated ask-user markup cannot supply prompt metadata
- **WHEN** model output contains `<ASK_USER_YAML>` or similar legacy ask-user
  markup
- **THEN** runtime MUST NOT populate canonical `PendingInteraction` fields from
  that markup
- **AND** only a valid pending JSON branch may supply rich waiting payload data
