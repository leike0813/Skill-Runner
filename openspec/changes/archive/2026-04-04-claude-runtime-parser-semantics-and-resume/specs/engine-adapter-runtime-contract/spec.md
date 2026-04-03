## MODIFIED Requirements

### Requirement: Claude parser extracts stable runtime semantics

Claude runtime parsing MUST extract the same minimal semantic surface style as the existing Codex and OpenCode parsers: stable session handle extraction, assistant text extraction, turn markers, and small `process_type/classification` vocabulary.

#### Scenario: Claude system init emits run handle

- **WHEN** Claude emits `type=system` with `subtype=init` and a valid `session_id`
- **THEN** the parser MUST expose `run_handle.handle_id = session_id`
- **AND** it MUST use that event as a valid turn-start anchor

#### Scenario: Claude tool rows map to stable process classifications

- **WHEN** Claude emits `assistant.tool_use` and `user.tool_result`
- **THEN** the parser MUST classify Bash/grep-style work as `command_execution`
- **AND** it MUST classify other tools as `tool_call`
- **AND** Claude-specific details MUST be carried in `details` instead of inventing new top-level classifications

#### Scenario: Claude thinking rows map to reasoning

- **WHEN** Claude emits `assistant.message.content[type=thinking]`
- **THEN** the parser MUST expose it as `process_type = reasoning`
- **AND** it MUST classify it as `reasoning`
- **AND** the thinking text MUST be preserved in `text`
