# Proposal: stabilize-runtime-resume-idempotency-and-attempt-ownership

## Why

The current in-conversation auth work fixed several local failures, but recent runs still show a deeper runtime contract gap:

- the same auth completion can be consumed more than once
- a single resume flow can materialize more than one `turn.started`
- `pending.json`, `history.jsonl`, `status.json`, and `result/result.json` can drift across attempts
- callback completion, `/auth/session` reconciliation, and restart recovery can race and each try to advance the same run

These are not auth-method-selection problems anymore. They are runtime canonical invariants about resume ownership, attempt materialization, and current-vs-history truth.

## What Changes

This change introduces a dedicated runtime-resume contract by:

1. defining single-consumer resume semantics for `waiting_auth` and `waiting_user`
2. making resumed execution materialize exactly one target attempt before `turn.started`
3. defining `current projection`, current pending, interaction history, and terminal result as separate truth layers
4. requiring callback completion, `/auth/session` reconcile, and restart recovery to share one canonical resume ownership path
5. extending runtime protocol/schema fields so the winning resume path and attempt boundaries are observable
6. making `client_metadata.conversation_mode` the only source of truth for whether a client may enter `waiting_auth` / real `waiting_user`
7. normalizing non-session execution so dual-mode skills default to `auto`, while interactive-only skills run as zero-timeout pseudo-interactive

More concretely, this change makes the current-state contract explicit:

- `current/projection.json` and durable projection storage become the only current truth
- `pending*.json` only describe the current waiting owner
- audit/history remain append-only attempt-scoped facts
- `result/result.json` becomes terminal-only and must not carry waiting snapshots

## Impact

- affects interactive lifecycle, runtime event schema, interactive job API, projection persistence, observability, and resume orchestration
- does not introduce a new top-level canonical state; `method_selection` remains an internal `waiting_auth` phase
- does not redefine existing auth methods or submission kinds from the previous auth-selection change
