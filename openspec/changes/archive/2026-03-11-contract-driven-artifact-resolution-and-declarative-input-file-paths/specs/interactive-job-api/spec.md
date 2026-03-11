## ADDED Requirements

### Requirement: jobs create API MUST accept declarative file input paths
The `POST /v1/jobs` API MUST accept file-sourced input values in the request body as `uploads/`-relative paths.

#### Scenario: create request carries inline and file inputs together
- **WHEN** a client submits mixed inline and file inputs in `input`
- **THEN** the backend accepts both in the same payload
- **AND** file values are treated as uploads-relative path references
