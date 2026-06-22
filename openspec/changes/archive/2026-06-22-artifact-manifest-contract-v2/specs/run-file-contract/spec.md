## ADDED Requirements

### Requirement: Artifact manifest semantics MUST be declared by x-type

The system MUST treat output fields marked with `x-type: "artifact-manifest"` as generated artifact manifest fields. `x-role` MUST remain a free-form role label and MUST NOT determine artifact manifest behavior.

#### Scenario: terminal result expands artifact manifest type
- **WHEN** a run reaches terminal normalization
- **AND** an output field has `x-type: "artifact-manifest"`
- **AND** the field points to a flat JSON object whose values are workspace-relative file paths or absolute paths inside the workspace
- **THEN** the system records the manifest file path in `result.json.artifacts`
- **AND** records every manifest value path in `result.json.artifacts`
- **AND** rewrites manifest values to workspace-relative POSIX paths before bundle assembly

#### Scenario: legacy artifact-manifest role has no special behavior
- **WHEN** a run reaches terminal normalization
- **AND** an output field has `x-type: "artifact"` and `x-role: "artifact-manifest"`
- **THEN** the system treats the field as an ordinary single artifact path
- **AND** does not expand the referenced file as an artifact manifest

#### Scenario: artifact manifest rejects workspace-external absolute paths
- **WHEN** an artifact manifest value is an absolute path outside the workspace
- **THEN** terminal normalization MUST fail the run
- **AND** the terminal result MUST include a clear `BUNDLE_ASSEMBLY_*` diagnostic
