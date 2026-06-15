## ADDED Requirements

### Requirement: New runner-owned terminal results MUST use actual result path
New runs SHALL write the runner-owned terminal result to the run's persisted `resultJsonPath`.

#### Scenario: New run writes namespaced result
- **WHEN** a new logical run is allocated namespace `<safeSkillId>.<n>`
- **THEN** its terminal result is written to `result/<safeSkillId>.<n>/result.json`
- **AND** callers MUST read the persisted actual result path rather than deriving `result/result.json`

#### Scenario: Legacy result path remains readable
- **GIVEN** a historical run has no persisted actual result path
- **WHEN** a caller reads the result
- **THEN** the system may fall back to `result/result.json`

### Requirement: New input manifests MUST use actual input manifest path
New runs SHALL write the runner-owned input manifest to the run's persisted `inputManifestPath`.

#### Scenario: New run writes namespaced input manifest
- **WHEN** a new logical run is allocated namespace `<safeSkillId>.<n>`
- **THEN** its runner-owned input manifest is written to `.audit/<safeSkillId>.<n>/input_manifest.json`

### Requirement: Package-owned result fallback MUST ignore runner-owned namespaces
Package-owned result fallback discovery SHALL exclude runner-owned result and audit subtrees.

#### Scenario: Fallback ignores runner-owned files
- **WHEN** lifecycle scans a workspace for a package-owned fallback result file
- **THEN** files under `result/` and `.audit/` do not participate in candidate selection

