## ADDED Requirements

### Requirement: output schema MUST support artifact-manifest x-type

The output schema meta-schema MUST allow `x-type: "artifact-manifest"` as a first-class artifact path marker. `x-type: "artifact"` and `x-type: "artifact-manifest"` fields MUST require a non-empty free-form `x-role`; `x-type: "artifact-manifest"` fields MUST be string fields.

#### Scenario: artifact manifest type passes validation
- **WHEN** `output.schema.json` contains a string field with `x-type: "artifact-manifest"` and a non-empty `x-role`
- **THEN** system package validation accepts the output schema

#### Scenario: artifact manifest type missing role is rejected
- **WHEN** `output.schema.json` contains a field with `x-type: "artifact-manifest"` but no non-empty `x-role`
- **THEN** system package validation rejects the output schema

#### Scenario: artifact-manifest role remains a plain role
- **WHEN** `output.schema.json` contains a string field with `x-type: "artifact"` and `x-role: "artifact-manifest"`
- **THEN** system package validation accepts the output schema
- **AND** runtime treats the field as an ordinary artifact field
