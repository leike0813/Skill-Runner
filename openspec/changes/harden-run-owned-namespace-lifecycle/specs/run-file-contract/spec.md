# run-file-contract Delta

## MODIFIED Requirements

### Requirement: New runner-owned terminal results MUST use actual result path
New request-bound runs SHALL write and read the runner-owned terminal result using the persisted actual `resultJsonPath`.

#### Scenario: Terminal finalization writes namespaced result
- **WHEN** a request-bound run with namespace `<safeSkillId>.<n>` reaches `succeeded`, `failed`, or `canceled`
- **THEN** terminal finalization writes `result/<safeSkillId>.<n>/result.json`
- **AND** run-store metadata records that actual result path
- **AND** no request-bound terminal finalization writes `result/result.json` as current truth.

#### Scenario: Result readers prefer actual result path
- **GIVEN** a request record has a persisted actual result path
- **WHEN** a caller reads the run result, artifacts, or bundle candidates
- **THEN** the persisted actual path is preferred
- **AND** `result/result.json` is used only as legacy fallback when no actual path is known.

### Requirement: New input manifests MUST use actual input manifest path
New request-bound runs SHALL write the runner-owned input manifest to the persisted `inputManifestPath`.

#### Scenario: Request snapshot writes namespaced input manifest
- **WHEN** a request-bound run is initialized with namespace `<safeSkillId>.<n>`
- **THEN** the request input snapshot is written to `.audit/<safeSkillId>.<n>/input_manifest.json`
- **AND** first-attempt prompt and spawn-command audit enrichment updates that same file.

## ADDED Requirements

### Requirement: Request-bound state files MUST use run-owned namespace
Request-bound run state and dispatch files MUST use the persisted workspace namespace whenever layout metadata exists.

#### Scenario: Queued and running state use namespaced state files
- **WHEN** a request-bound run is initialized, admitted, scheduled, claimed, or marked running
- **THEN** the backend writes `.state/<namespace>/state.json`
- **AND** dispatch phase writes `.state/<namespace>/dispatch.json`
- **AND** root `.state/state.json` is not updated as current truth for that request-bound run.

#### Scenario: Queued initialization refetches layout after request binding
- **GIVEN** a request was bound to a run after an earlier request record was loaded
- **WHEN** queued state is initialized with that stale request record
- **THEN** the backend refetches the bound request metadata before resolving state paths
- **AND** initialization still writes `.state/<namespace>/state.json` and `.state/<namespace>/dispatch.json`.

#### Scenario: Interaction and auth callbacks update namespaced state
- **WHEN** reply, auth selection, auth input, auth import, auth status reconciliation, or auth timeout updates current status for a request-bound run
- **THEN** the update targets `.state/<namespace>/state.json`
- **AND** root `.state/state.json` is only used when no layout metadata exists.

### Requirement: Package-owned fallback scans MUST not confuse runner-owned namespace files
Fallback scans for package-owned outputs SHALL keep runner-owned state, audit, and result namespaces separate from package-owned artifacts.

#### Scenario: Result fallback excludes runner-owned namespaces
- **WHEN** lifecycle scans a workspace for package-owned fallback output
- **THEN** files under `result/`, `.state/`, and `.audit/` are not treated as package-owned output candidates.

### Requirement: Request-bound bundles MUST use run-owned namespace
Request-bound bundle zip files and manifests MUST use the persisted workspace namespace whenever layout metadata exists.

#### Scenario: Bundle generation writes namespaced bundle files
- **WHEN** a request-bound run with namespace `<safeSkillId>.<n>` succeeds
- **THEN** the backend writes `bundle/<safeSkillId>.<n>/run_bundle.zip`
- **AND** debug bundle generation writes `bundle/<safeSkillId>.<n>/run_bundle_debug.zip`
- **AND** the corresponding manifests are written in that same bundle namespace directory
- **AND** root `bundle/run_bundle*.zip` is not updated as current truth for that request-bound run.

#### Scenario: Bundle collection only includes the current namespace
- **GIVEN** a reused workspace contains multiple result namespaces
- **WHEN** the caller downloads a bundle for one request
- **THEN** the bundle includes that request's actual `resultJsonPath`
- **AND** it may include `_skill_run_feedback.md` from the same result directory
- **AND** it may include artifacts referenced by that result payload
- **AND** it does not include result, audit, state, feedback, or artifact files solely owned by another namespace.
