## MODIFIED Requirements

### Requirement: Artifact contract MUST be driven by output artifact-path fields
The system MUST treat output fields marked with `x-type: artifact|file` as the canonical artifact contract. Fields marked `x-type: "artifact"` MUST declare a non-empty `x-role`.

#### Scenario: terminal result resolves ordinary artifact paths
- **WHEN** a run reaches terminal normalization
- **AND** an output field has `x-type: "artifact"` with `x-role` other than `artifact-manifest`
- **THEN** the system resolves the field value to a run-local file
- **AND** rewrites the field to a workspace-relative bundle entry path
- **AND** records that path in `result.json.artifacts`

#### Scenario: terminal result expands artifact manifest paths
- **WHEN** a run reaches terminal normalization
- **AND** an output field has `x-type: "artifact"` and `x-role: "artifact-manifest"`
- **AND** the field points to a flat JSON object whose values are workspace-relative file paths
- **THEN** the system records the manifest file path in `result.json.artifacts`
- **AND** records every manifest value path in `result.json.artifacts`
- **AND** bundle zip entries match the path strings recorded in JSON

#### Scenario: artifact manifest assembly diagnostic
- **WHEN** an artifact manifest is unreadable, invalid JSON, not a flat object, contains non-string path values, contains invalid paths, or references missing files
- **THEN** terminal normalization MUST fail the run
- **AND** the terminal result MUST include a clear `BUNDLE_ASSEMBLY_*` diagnostic

### Requirement: ordinary bundles MUST be contract-driven
Non-debug bundles MUST include the request's actual `resultJsonPath` and resolved artifact files.

#### Scenario: declared artifact path is missing during bundle assembly
- **WHEN** a bundle is built
- **AND** `result.json.artifacts` contains an invalid or missing workspace-relative file path
- **THEN** bundle assembly MUST fail with a structured `BUNDLE_ASSEMBLY_*` diagnostic
- **AND** the backend MUST NOT silently omit the declared entry

