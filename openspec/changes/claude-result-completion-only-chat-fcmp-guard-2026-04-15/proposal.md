## Why

Run `98834187-7004-4f7d-8ebf-b326d3a15c6b` exposed two governance problems in the Claude runtime
path:

1. Claude `type=result` rows were treated both as completion metadata and as ordinary assistant
   body text, so a result echo could register a second message candidate and get promoted as the
   final message.
2. The repository already derives chat replay from published FCMP rows, but there was no explicit
   OpenSpec change or regression guard locking that invariant. That left room for future parser-side
   shortcuts to bypass the runtime event lane.

This change formalizes and implements the fix at the parser boundary, while also tightening the
governance rule that chat remains an FCMP-derived view.

## What Changes

- Make Claude `type=result` completion-only by default in both batch runtime parsing and live NDJSON
  parsing.
- Keep a narrow Claude-only fallback that emits `result.result` as an assistant message only when
  the turn has no real assistant body message and no `structured_output`.
- Mark that fallback with `details.source = "claude_result_fallback"` so it is auditable and cannot
  be confused with normal assistant body text.
- Preserve Claude `result` completion metadata (`turn_complete`, `result_subtype`, usage data) while
  removing default promotion eligibility for `result.result`.
- Add regression coverage proving chat replay is published from committed FCMP rows and not directly
  from parser emissions.

## Capabilities

### Modified Capabilities

- `engine-adapter-runtime-contract`: Claude `result` rows now default to completion-only semantics,
  with a narrow fallback assistant-message path.
- `interactive-job-api`: final/promotion semantics now exclude normal Claude `result` echoes from the
  message candidate pool.
- `interactive-run-observability`: runtime observability now preserves a source marker for Claude
  fallback messages and keeps completion metadata separate from ordinary message semantics.
- `canonical-chat-replay`: chat replay governance now explicitly requires FCMP-derived publication
  and forbids parser-to-chat shortcuts.

## Impact

- Affected code: Claude stream parser, shared live publish assistant-message detail propagation, and
  runtime event / chat replay regression tests.
- Affected tests: Claude parser tests, live emitter tests, chat replay derivation tests, live publish
  ordering tests, and runtime event protocol regressions.
- Public HTTP API, FCMP/RASP wire shape, and chat replay schema remain unchanged.
