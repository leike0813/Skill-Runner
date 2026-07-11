## ADDED Requirements

### Requirement: The built-in example client MUST require a CodeBuddy provider before model selection

The existing `/skills/{skill_id}/run` flow MUST derive CodeBuddy providers from engine detail metadata, start with no provider selected, disable model selection until a provider is chosen, and then show only models belonging to that provider. Model omission remains valid.

#### Scenario: User changes CodeBuddy provider
- **WHEN** the selected provider changes
- **THEN** an incompatible model and reasoning effort are cleared and only the new provider's models remain selectable

### Requirement: Example-client validation MUST fail closed

The example client server MUST reject a missing or unknown CodeBuddy provider and any provider/model mismatch before calling the backend job API.

#### Scenario: Global provider is submitted with a domestic-only model
- **WHEN** the run form is submitted
- **THEN** the client returns HTTP 400 and does not create a job
