## MODIFIED Requirements

### Requirement: E2E run form supports Claude custom-provider models

The built-in E2E example client SHALL consume the merged Claude model catalog and allow selecting strict `provider/model` entries.

#### Scenario: render Claude run form models

- **WHEN** the E2E run form loads Claude models
- **THEN** it MUST include official snapshot models
- **AND** it MUST include configured custom-provider models
- **AND** third-party models MUST be submitted as strict `provider/model`
