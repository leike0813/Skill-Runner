## Design

### Structured-output success as a generic capability

Adapter profiles gain a machine-readable structured-output success-result strategy. Claude uses `result_structured_output_field` and future engines such as OpenCode can reuse the same capability.

Runtime parser capabilities also record whether an engine can extract structured output directly from a success result.

### Success source

The orchestrator records the final accepted success source. Initial governed values:

- `structured_output_result`
- `structured_output_candidate`
- `done_signal_payload`
- `done_marker_fallback`
- `result_file_fallback`

This value becomes the machine-readable truth across:

- convergence results
- resolved outcome
- attempt audit metadata
- terminal/result payloads

### Observability

Accepted structured-output success reuses the existing final chain:

- parser emits an assistant message candidate representing the structured-output result
- RASP `agent.message.final` keeps the parser-provided source details
- FCMP `assistant.message.final` exposes a stable `display_origin`
- chat replay uses the accepted final as the winner

### Done marker fallback

Done-marker logic moves behind all explicit structured-output paths and repair.

Only explicit `__SKILL_DONE__ = true` payloads are accepted for fallback completion. Regex scanning of arbitrary assistant text no longer participates in normal success precedence.
