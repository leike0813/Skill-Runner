# Design

## Command Defaults

OpenCode and Kilo enable thinking through profile command defaults rather than command-builder branches. This keeps engine-specific CLI defaults in the adapter profile and preserves the existing `--dir`, `--session`, and `--model` composition rules.

OpenCode adds `--thinking` next to `--format json`. Kilo adds `--thinking` before the resume `--session` marker so the existing builder can continue appending the session id after `--session`.

## Shared Parser

`OpenCodeFamilyStreamParserCore` becomes the single parser for OpenCode-family explicit reasoning rows. It treats `type=reasoning` with `part.text` as a `RuntimeProcessEvent` with `process_type=reasoning`; top-level `text` is accepted as a fallback for compatibility.

The event is emitted through the same process-event path used by tool calls. Existing runtime protocol projection already maps reasoning process events to `agent.reasoning` and `assistant.reasoning`, so no new protocol event type is introduced.

## Boundaries

Reasoning text is process/audit data, not an assistant message. Legacy `parse(raw_stdout)` continues to use text rows only, and `step_finish.part.tokens.reasoning` remains usage metadata unless an explicit reasoning text row is present.
