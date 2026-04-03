## MODIFIED Requirements

### Requirement: Claude Runtime Parsing Emits Stable Semantic Events

Claude runtime parsing MUST attach stable `raw_ref` evidence to semantic-consumed rows, including `system/init`, assistant text/tool-use content, tool results, and terminal `result` rows.

#### Scenario: semantic-consumed Claude rows are not re-emitted as raw stdout
- **WHEN** Claude stream parsing successfully classifies runtime rows into semantic outputs
- **THEN** overlapping rows MUST be suppressed from `raw_rows`
- **AND** only truly unclassified or unconsumed rows may remain in `raw_rows`

### Requirement: Claude Sandbox Problems Are Warning-Level Diagnostics

Claude sandbox dependency or runtime failures MUST be observable as warnings without changing the run into a hard preflight failure by themselves.

#### Scenario: Claude sandbox dependency missing
- **WHEN** `bubblewrap`/`bwrap` or `socat` is unavailable
- **THEN** the system MUST emit a stable Claude sandbox warning code
- **AND** the run/preflight result MUST remain warning-only unless another blocking failure exists
