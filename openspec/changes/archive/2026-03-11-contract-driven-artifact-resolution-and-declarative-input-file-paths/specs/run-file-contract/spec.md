## ADDED Requirements

### Requirement: Artifact contract MUST be driven by output artifact-path fields
The system MUST treat output fields marked with `x-type: artifact|file` as the canonical artifact contract.

#### Scenario: terminal result resolves artifact paths
- **WHEN** a run reaches terminal normalization
- **THEN** the system resolves each output artifact-path field to a run-local file
- **AND** rewrites the field to a bundle-relative path

### Requirement: required artifact validation MUST use resolved file existence
The system MUST validate required artifacts by checking the declared output field and the resolved file, rather than a fixed `artifacts/<pattern>` path.

#### Scenario: dynamic file name passes after resolve
- **GIVEN** a required output artifact field points to a real file with a dynamic file name
- **WHEN** terminal validation runs
- **THEN** the run passes artifact validation

### Requirement: ordinary bundles MUST be contract-driven
Non-debug bundles MUST include only `result/result.json` and resolved artifact files.

#### Scenario: uploads and temp files are excluded from normal bundle
- **WHEN** a non-debug bundle is built
- **THEN** uploads and unrelated working files are excluded
- **AND** resolved artifact files are included regardless of whether they live under `artifacts/`

### Requirement: file inputs MUST support declarative uploads-relative paths
File inputs MUST be expressible as `uploads/`-relative paths in `POST /v1/jobs`.

#### Scenario: file input declared as uploads-relative path
- **WHEN** a client submits `input.paper = \"papers/a.pdf\"`
- **AND** upload zip contains `papers/a.pdf`
- **THEN** runtime resolves the file to the uploaded file and injects its absolute path

#### Scenario: file path omitted falls back to strict-key compatibility
- **WHEN** a file input key is not explicitly provided in the request body
- **THEN** runtime MAY still resolve `uploads/<input_key>` as a compatibility fallback
