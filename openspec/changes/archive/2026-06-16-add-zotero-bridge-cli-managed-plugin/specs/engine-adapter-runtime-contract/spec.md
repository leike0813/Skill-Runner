## MODIFIED Requirements

### Requirement: Adapter subprocess env MUST support run-local overlays

Execution adapters SHALL apply request-scoped runtime env only to the current subprocess environment after engine profile env construction and before command execution. Managed deployment defaults that are not request secrets, such as `ZOTERO_BRIDGE_PROFILE`, MAY be supplied by the runtime profile and MUST remain overrideable by the request-local env overlay.

#### Scenario: injected env reaches current subprocess
- **WHEN** attempt run options contain internal `__runtime_env`
- **THEN** adapter subprocess creation receives those key/value pairs in its env
- **AND** dependency probes and wrapped uv commands receive the same env

#### Scenario: injected env does not mutate global process env
- **WHEN** adapter applies runtime env for a run
- **THEN** it MUST NOT mutate `os.environ`
- **AND** a later run without runtime env MUST NOT inherit the previous values

#### Scenario: managed bridge profile env is available by default
- **WHEN** an agent subprocess environment is built
- **THEN** it includes `ZOTERO_BRIDGE_PROFILE` pointing at the managed profile path
- **AND** request-local runtime env can override endpoint, token, and connection mode for only that run
