# Design

## Core model

Phase 4 keeps the phase-3B convergence contract intact and only changes how
`waiting_user` payloads are sourced.

- rich pending payloads come only from a valid pending JSON branch
- unresolved interactive attempts may still fall back to `waiting_user`
- fallback waiting payloads are always default/generic

## Waiting source order

For interactive attempts:

1. If convergence resolves the pending branch, project it directly into
   canonical `PendingInteraction`.
2. If convergence resolves the final branch, continue with the existing success
   or failure rules.
3. If convergence does not resolve a valid branch and lifecycle still decides
   that the attempt may wait, synthesize a default pending payload with:
   - `kind = open_text`
   - `prompt = DEFAULT_INTERACTION_PROMPT`
   - empty `options`
   - empty `ui_hints`

## Legacy deletion boundary

The runtime removes legacy enrichment as authoritative waiting input.

- deprecated `<ASK_USER_YAML>` and fenced ask-user blocks no longer populate
  waiting payload fields
- runtime-stream message parsing no longer recovers prompt or hints for waiting
- direct interaction-like payloads no longer populate waiting payload fields
- the deprecated helpers may be removed or reduced to no-op / default builders

## Non-goals

- do not tighten final completion to require explicit `__SKILL_DONE__ = true`
- do not remove interactive soft completion
- do not change public `PendingInteraction` structure
- do not add new protocol event types
