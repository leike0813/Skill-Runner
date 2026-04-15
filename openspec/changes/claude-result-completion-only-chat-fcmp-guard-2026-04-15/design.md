## Context

Claude stream-json turns can contain both ordinary assistant body rows and a terminal
`{"type":"result"}` row. The observed bug was caused by treating `result.result` as if it were
another assistant body message:

- the live parser emitted an `assistant_message`
- the batch runtime parser appended to `assistant_messages`
- the promotion coordinator, which is intentionally engine-agnostic, promoted the newest candidate
  and therefore selected the `result` echo instead of the real assistant body

Chat replay itself was not the primary root cause. It already derives from published FCMP rows.
However, the repository lacked an explicit governance guard proving that parser semantics must pass
through the runtime event lane before chat replay is written.

## Goals / Non-Goals

**Goals**

- Make Claude `type=result` completion-only by default.
- Preserve the existing completion metadata carried by Claude `result` rows.
- Allow a narrow fallback assistant message only when there is no better textual body source.
- Keep chat replay derived from FCMP and add regression guards against parser shortcuts.

**Non-Goals**

- Reworking the generic final promotion coordinator.
- Changing chat replay to derive from RASP instead of FCMP.
- Changing public API schemas, FCMP event types, or chat replay wire shape.
- Broadening this fix into other engine-specific result/done semantics.

## Decisions

### 1. Claude `result` is completion-lane only by default

Both Claude batch runtime parsing and live stream parsing now treat `type=result` as completion
metadata first:

- it still emits turn completion markers
- it still carries `result_subtype` and usage data
- it no longer creates a normal assistant message candidate by default

Rationale:

- The result row is a completion summary, not a canonical body-text source.
- Fixing this at the parser boundary keeps the shared promotion coordinator engine-agnostic.

### 2. Claude keeps a narrow fallback assistant-message path

`result.result` may still become an assistant message only when all of the following are true:

- the current turn has no real assistant text body
- the result row has no `structured_output`
- `result.result` is non-empty

Fallback messages must carry `details.source = "claude_result_fallback"`.

Rationale:

- Some Claude turns may complete with textual summary only.
- The explicit source marker prevents confusion between true assistant body text and fallback text.

### 3. Promotion semantics remain shared and engine-agnostic

The final promotion coordinator is unchanged. Claude-specific filtering happens before message
candidates enter the pool.

Rationale:

- Promotion logic should continue to operate on already-normalized message candidates.
- Engine-specific exceptions inside promotion would cause governance drift and make future regressions
  harder to reason about.

### 4. Chat replay remains FCMP-derived and must not accept parser shortcuts

This change does not alter the existing architecture:

- parsers emit semantics
- runtime publishers validate and publish RASP/FCMP rows
- chat replay derives only from committed FCMP rows

The new regression guard checks that chat publication happens only after FCMP commit and with the
committed FCMP row payload.

Rationale:

- Chat correctness should be downstream of canonical runtime events, not parser-local heuristics.
- Fixing the Claude result bug by patching chat directly would hide the upstream semantic defect.

## Risks / Trade-offs

- [Loss of Claude result text in normal structured-output turns] -> Accepted, because that text is a
  duplicate completion echo and should not compete with real assistant body text.
- [Fallback path may still emit text in rare Claude-only turns] -> Accepted, because the fallback is
  explicit, narrow, and auditable via `details.source`.
- [Governance test does not prove every future call site] -> Mitigated by asserting the committed
  FCMP row is the only input to chat replay publishing in the shared FCMP publisher.
