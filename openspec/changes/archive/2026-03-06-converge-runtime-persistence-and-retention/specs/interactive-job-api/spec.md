## ADDED Requirements

### Requirement: Temporary skill upload SHALL remain on unified jobs API
Temporary skill upload runs SHALL use the unified `/v1/jobs` create/upload flow and SHALL NOT require a separate temp-skill API family.

#### Scenario: Legacy temp-skill endpoint access
- **WHEN** a client calls `/v1/temp-skill-runs/*`
- **THEN** the API SHALL return not found semantics (404)

### Requirement: Upload staging SHALL be runtime-internal and data-dir scoped
During `/v1/jobs/{request_id}/upload`, temporary extraction staging SHALL occur under server data root and be cleaned up after upload flow completion.

#### Scenario: Upload staging and cleanup
- **WHEN** upload processing starts for a request
- **THEN** the server SHALL stage files under `data/tmp_uploads/<request_id>`
- **AND** after success or failure, the server SHALL perform best-effort deletion of that request staging directory
