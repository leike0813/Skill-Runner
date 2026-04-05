## ADDED Requirements

### Requirement: Qwen stream parser MUST support runtime stream parsing

The Qwen engine stream parser SHALL implement `parse_runtime_stream` method to support real-time event extraction from NDJSON output.

#### Scenario: Parse Qwen stream-json output

- **WHEN** Qwen emits NDJSON events during execution
- **THEN** the parser MUST extract `system/subtype=init` for session handle recovery
- **AND** it MUST extract `assistant.message.content[].type=text` for assistant text messages
- **AND** it MUST extract `assistant.message.content[].type=thinking` as `process_events` classified as `reasoning`
- **AND** it MUST extract `assistant.message.content[].type=tool_use` and `user.message.content[].type=tool_result` as `process_events`
- **AND** it MUST extract `result` payloads for turn completion
- **AND** it MUST return a `RuntimeStreamParseResult` with `session_id`, `assistant_messages`, `process_events`, `turn_markers`, and `auth_signal`

#### Scenario: Qwen parser returns standard parse result

- **WHEN** `parse_runtime_stream` completes
- **THEN** it MUST return a dictionary with keys: `parser`, `confidence`, `session_id`, `assistant_messages`, `turn_started`, `turn_completed`, `turn_markers`, `raw_rows`, `diagnostics`, `structured_types`
- **AND** `parser` MUST be `"qwen_ndjson"`
- **AND** `confidence` MUST be `0.95` if `turn_completed`, `0.75` if `assistant_messages`, `0.5` otherwise

### Requirement: Qwen stream parser MUST support live session

The Qwen engine stream parser SHALL implement `start_live_session` method returning a `LiveStreamParserSession` for incremental event emission.

#### Scenario: Create Qwen live parser session

- **WHEN** the runtime creates a live parser session for Qwen engine
- **THEN** it MUST return a `_QwenLiveSession` instance
- **AND** the session MUST accept `stdout` and `pty` streams

#### Scenario: Live session emits run_handle

- **WHEN** the live session parses a `system/subtype=init` event
- **THEN** it MUST emit a `run_handle` emission with `handle_id` from `session_id`
- **AND** it MUST emit this only once per session

#### Scenario: Live session emits assistant_message

- **WHEN** the live session parses an `assistant` event with `text` content blocks
- **THEN** it MUST emit an `assistant_message` emission with the extracted text

#### Scenario: Live session emits semantic process events

- **WHEN** the live session parses `thinking`, `tool_use`, or `tool_result` blocks
- **THEN** it MUST emit `process_event` emissions
- **AND** `thinking` MUST classify as `reasoning`
- **AND** `run_shell_command` MUST classify as `command_execution`
- **AND** other qwen tools MUST classify as `tool_call`

#### Scenario: Live session emits turn_marker

- **WHEN** the live session observes `system/subtype=init` or the first `assistant` event
- **THEN** it MUST emit a `turn_marker` emission with `marker: "start"`
- **WHEN** the live session parses a `result` event
- **THEN** it MUST emit a `turn_marker` emission with `marker: "complete"`
- **AND** if `usage` is present, it MUST include `turn_complete_data`

### Requirement: Qwen parser MUST detect auth signals

The Qwen runtime stream parser SHALL call `detect_auth_signal_from_patterns` with appropriate stdout/stderr/pty evidence for auth failure detection.

#### Scenario: Detect Qwen OAuth token expired

- **WHEN** stdout/stderr/pty combined text contains OAuth token expired patterns
- **THEN** the parser MUST return an `auth_signal` in the parse result
- **AND** the signal MUST reference the matched rule `qwen_oauth_token_expired`

#### Scenario: Detect Qwen API key missing

- **WHEN** stdout/stderr/pty combined text contains API key missing patterns
- **THEN** the parser MUST return an `auth_signal` in the parse result
- **AND** the signal MUST reference the matched rule `qwen_api_key_missing`

#### Scenario: Detect Qwen OAuth device flow waiting authorization

- **WHEN** `parse_runtime_stream(stdout/stderr/pty)` sees the OAuth device flow waiting banner in combined stream text
- **THEN** the parser MUST return an `auth_signal` in the parse result
- **AND** the signal MUST reference the matched rule `qwen_oauth_waiting_authorization`
- **AND** the `reason_code` MUST be `QWEN_OAUTH_WAITING_AUTHORIZATION`

#### Scenario: Qwen waiting auth remains actionable when request provider is missing

- **WHEN** Qwen `parse_runtime_stream(stdout/stderr/pty)` yields an auth signal matching `qwen_oauth_waiting_authorization`
- **AND** the original request did not carry an explicit `provider_id`
- **THEN** the standard auth orchestration path MUST still be able to enter `waiting_auth`
- **AND** it MUST normalize the provider to `qwen-oauth` before creating the pending auth challenge

#### Scenario: Stderr auth banner does not become a live semantic event

- **WHEN** Qwen prints a non-NDJSON OAuth waiting banner on `stderr`
- **THEN** `start_live_session()` MUST NOT emit assistant or turn semantic events for that banner
- **AND** the banner MUST still remain detectable through `parse_runtime_stream(stdout/stderr/pty)`

### Requirement: Qwen adapter MUST be fully functional

The Qwen engine adapter SHALL have complete stream parser implementation for both batch and live parsing modes.

#### Scenario: Qwen adapter provides complete parser

- **WHEN** the engine adapter registry is initialized
- **THEN** `QwenExecutionAdapter.stream_parser` MUST have `parse_runtime_stream` method implemented
- **AND** `QwenExecutionAdapter.stream_parser.start_live_session()` MUST NOT raise `NotImplementedError`

### Requirement: Qwen NDJSON event types

The Qwen stream parser SHALL recognize and process the following NDJSON event types:

| Event Type | Source | Parser Action |
|------------|--------|---------------|
| `system` + `subtype=init` | stdout | Extract `session_id` as `run_handle.handle_id` and mark canonical turn start |
| `assistant.message.content[].type=thinking` | stdout | Extract as `process_event(reasoning)` |
| `assistant.message.content[].type=tool_use` | stdout | Extract as `process_event(tool_call/command_execution)` |
| `assistant.message.content[].type=text` | stdout | Extract as `assistant_message` |
| `user.message.content[].type=tool_result` | stdout | Extract as `process_event(tool_call/command_execution)` |
| `result` | stdout | Mark `turn_complete`, extract `usage` as `turn_complete_data` |

#### Scenario: Session ID extraction

- **WHEN** Qwen emits `system/subtype=init`
- **THEN** the parser MUST extract `session_id` field
- **AND** use it for `run_handle.handle_id`

#### Scenario: Assistant text extraction

- **WHEN** Qwen emits `assistant` event with `message.content` array
- **THEN** the parser MUST iterate content blocks
- **AND** extract `text` type blocks for `assistant_message.text`

#### Scenario: Assistant process extraction

- **WHEN** Qwen emits `assistant` or `user` events with `thinking`, `tool_use`, or `tool_result` blocks
- **THEN** the parser MUST emit `process_events`
- **AND** `thinking` MUST classify as `reasoning`
- **AND** tool results MUST inherit the corresponding tool classification when the `tool_use_id` can be resolved

#### Scenario: Result turn completion

- **WHEN** Qwen emits `result` event
- **THEN** the parser MUST set `turn_completed: true`
- **AND** if `usage` object exists, include it in `turn_complete_data`

#### Scenario: Duplicate final text is suppressed

- **WHEN** the final `assistant text` content and `result.result` normalize to the same text
- **THEN** the parser MUST keep only one assistant final candidate
- **AND** the live semantic path MUST NOT emit duplicate final message candidates for the same text
