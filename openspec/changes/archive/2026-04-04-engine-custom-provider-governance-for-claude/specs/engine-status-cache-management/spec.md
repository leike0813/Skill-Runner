## MODIFIED Requirements

### Requirement: Claude model catalog merges official and custom-provider models

Claude model discovery SHALL expose a merged catalog containing official snapshot models and configured custom-provider models.

#### Scenario: list Claude models

- **WHEN** management, UI, or E2E asks for Claude models
- **THEN** the catalog MUST include official snapshot models
- **AND** it MUST include configured custom-provider models rendered as `provider/model`
- **AND** each model entry MUST expose `source=official|custom_provider`

### Requirement: Claude third-party models require strict provider/model matching

Claude SHALL only accept third-party models via strict `provider/model` syntax.

#### Scenario: validate custom provider model

- **WHEN** a caller submits a third-party Claude model
- **THEN** the system MUST require `provider/model`
- **AND** it MUST reject bare third-party model names
