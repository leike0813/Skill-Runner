# Proposal

## Why

Phase 3B made the interactive pending JSON branch the formal contract, but the
runtime still preserves legacy waiting enrichment paths that can recover prompt,
kind, options, and hint details from deprecated YAML wrappers, runtime-stream
text, or direct interaction-like payloads.

That leaves `waiting_user` with two unresolved problems:

- the formal pending JSON branch is not yet the clear primary source of
  `PendingInteraction`
- legacy waiting fallbacks still carry protocol-shaped information that should
  no longer be authoritative

## What Changes

Phase 4 cuts over the primary waiting source to the pending JSON branch while
retaining a narrow legacy waiting fallback.

- pending JSON branch becomes the only rich-data source for `PendingInteraction`
- legacy waiting fallback remains available for unresolved interactive attempts
- legacy fallback always produces a default `PendingInteraction`
- YAML / runtime-stream / direct-payload enrichment logic is removed from the
  waiting path
- interactive soft completion remains unchanged in this phase

## Impact

- no public API or FCMP wire-shape change
- no change to `PendingInteraction` external schema
- interactive waiting continues to work, but legacy fallback payloads become
  generic instead of content-derived
