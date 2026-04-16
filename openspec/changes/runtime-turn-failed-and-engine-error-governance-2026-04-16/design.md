## Design Summary

This change separates two concerns that were previously conflated in raw engine output:

1. **semantic turn failure**: explicit engine-native `turn.failed` rows that should become canonical RASP `agent.turn_failed`
2. **diagnostic engine errors**: generic `type:"error"` and `item.type:"error"` rows that should remain raw evidence and also surface as `diagnostic.warning`

The implementation lands in a staged path, but the contract is simple:

- raw evidence is always preserved
- `agent.turn_failed` becomes the semantic turn-failure source for RASP
- generic error-like rows become diagnostics, not lifecycle truth
- terminal user-facing failure messages prefer semantic turn-failure summaries over generic process exit text

## Key Decisions

### `agent.turn_failed` is RASP-only

The new event is added only to RASP. FCMP continues to expose terminal failure through `conversation.state.changed(... trigger=turn.failed)` and does not get a new public event type.

### Generic engine errors reuse `diagnostic.warning`

The change does not add a new diagnostic type. Generic engine `error` rows and `item.type:error` rows are normalized into existing `diagnostic.warning` with richer payload metadata:

- `code`
- `severity`
- `pattern_kind`
- `source_type`
- `message`

This keeps the surface area small and reuses the existing diagnostics channel already consumed by observability and UI diagnostics.

### Terminal failure summary prefers semantic message sources

Terminal error-message priority becomes:

1. semantic `agent.turn_failed.message`
2. canonical auth / timeout / session failure summaries
3. structured-output / validation summaries
4. process failure reason
5. `Exit code N`

This change does not introduce a fallback where generic diagnostics become user-facing terminal text. That remains future work.

### Codex closes the first loop, helpers are cross-engine ready

This change fully closes the loop for Codex, because the failing sample already exists there. The diagnostic pattern-classification helper is implemented in a reusable way so other engine parsers can adopt it later without changing protocol shape.
