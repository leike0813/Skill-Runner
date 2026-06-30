## Context

Kilo emits the same runtime JSONL family as OpenCode for core stream rows:

- `step_start`
- `text`
- `tool_use`
- `step_finish`

The inspected samples did not contain independent reasoning/thinking text rows. They only exposed `step_finish.part.tokens.reasoning`, which is usage metadata rather than assistant reasoning content.

OpenCode already parses `tool_use` into `RuntimeProcessEvent`; Kilo does not. Maintaining a second Kilo parser would repeat the same mapping and risk drift.

## Design Decisions

1. **Use an OpenCode-family parser core**
   Shared runtime stream parsing lives under `server/engines/common/opencode_family`, keeping OpenCode-family protocol knowledge inside the engine domain. OpenCode and Kilo keep small adapter-local wrappers for legacy `parse(raw_stdout)` and engine-specific auth/error evidence.

2. **Process events come from all structured rows**
   Assistant message promotion may still use latest-step semantics, but `tool_use` process events must be extracted from the full stream so multi-step runs do not lose earlier tool activity.

3. **Kilo errors remain Kilo-specific**
   Kilo `type=error` rows continue to produce `turn_failed` and auth signal evidence. OpenCode keeps its existing auth evidence extraction without being changed into a failed-turn parser.

4. **Reasoning tokens are usage data**
   `tokens.reasoning` remains inside `turn_complete_data.tokens`. It does not create `agent.reasoning` unless a future Kilo stream adds explicit reasoning text rows.

5. **Terminal failure fallback is protocol-level**
   Parser code should not infer timeout/cancel reasons. RASP projection receives attempt status/completion metadata and emits fallback `agent.turn_failed` only when the parser has not already supplied one.

## Architecture

### Common parser core

The common core owns:

- OpenCode-family turn start/finish detection
- text extraction
- `tool_use` to `RuntimeProcessEvent`
- session/run-handle extraction
- live `process_event` emission
- parser confidence and raw fallback diagnostics

Adapter wrappers provide:

- parser name
- engine name
- auth rules
- optional error extractor
- optional fixed provider id for auth evidence

### Protocol projection

`build_rasp_events()` already projects `process_events` into RASP agent events and `build_fcmp_events()` already maps those agent events into FCMP assistant process events. The implementation should use those existing paths and avoid new event names.

For interrupted terminal attempts without parser failure evidence, `build_rasp_events()` emits fallback `agent.turn_failed` with `fatal=true`, status, completion state, and reason code.

## Failure Handling

- Malformed JSON rows continue to be captured as raw fallback diagnostics.
- Unknown `tool_use` tools map to `tool_call`.
- Empty stdout/stderr interrupted runs still produce lifecycle events and fallback failure evidence.
- If Kilo emits `type=error`, that semantic failure remains authoritative and fallback does not duplicate it.
