# Design

## Core rule

`agent.turn_failed` and `waiting_auth` live at different layers:

- `agent.turn_failed` = semantic engine evidence
- `waiting_auth` = canonical orchestration decision

They may coexist. When both are present, canonical state MUST remain `waiting_auth`, and `agent.turn_failed` MUST be treated as evidence-only for audit and user explanation.

## Precedence

The lifecycle normalization order stays the same:

1. Parse runtime stream and auth evidence
2. Attempt pending-auth materialization for high-confidence auth
3. If pending auth is created, normalize to `waiting_auth`
4. Otherwise fall back to `failed`

This change only makes the precedence explicit and preserves the semantic message.

## Waiting-auth message preservation

The waiting-auth UI already renders `pending_auth.last_error` and `instructions`. Reusing that surface is lower risk than adding a new protocol field or changing chat replay.

Message source priority for waiting-auth display:

1. semantic `turn_failed.message`
2. auth-related / entitlement-related diagnostic message extracted from runtime diagnostics
3. generic `"Authentication is required to continue."` fallback

The selected message is passed into auth orchestration and persisted into:

- `pending_auth.last_error`
- `pending_auth.instructions` (`Last error: ...`)
- `pending_auth_method_selection.last_error`
- `pending_auth_method_selection.instructions`

## Codex usage-limit classification

Codex usage-limit rows are not generic terminal failures in this system. They are recoverable entitlement/auth blockers and should therefore:

- stay in raw evidence
- continue emitting `diagnostic.warning`
- still emit `agent.turn_failed` when a semantic `turn.failed` row exists
- additionally match a high-confidence Codex auth pattern so the run can enter `waiting_auth`

This is implemented in Codex parser auth patterns rather than a special-case branch in orchestration.
