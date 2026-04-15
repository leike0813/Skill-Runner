# Proposal

## Why

Phase 4 completed the waiting-side source cutover, but the interactive
completion gate is still described inconsistently across specs and docs.

The runtime already preserves three distinct paths:

- explicit final branch
- explicit pending branch
- compatibility fallback paths (`soft completion` and default waiting fallback)

What is still missing is a stable phase-5 contract for their ordering and
status:

- explicit final / pending branches must be the formal contract
- soft completion must remain available, but only as a compatibility completion
  path
- waiting fallback must remain available, but only after explicit branches and
  soft completion fail
- the existing diagnostic codes must remain stable

## What Changes

Phase 5 tightens the interactive completion gate without doing a hard legacy
cutover.

- runtime documents and enforces the priority order:
  `final branch -> pending branch -> soft completion -> waiting fallback`
- soft completion remains supported when structured business output is valid
  without an explicit done marker
- waiting fallback remains supported when neither explicit branch nor soft
  completion applies
- existing warning and diagnostic codes remain unchanged
- public API and protocol shapes remain unchanged

## Impact

- no HTTP API shape change
- no FCMP or RASP public wire-shape change
- no `PendingInteraction` external schema change
- interactive completion semantics become easier to reason about and audit
- specs and docs stop drifting from the current conservative runtime behavior
