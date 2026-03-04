# Proposal: refine-in-conversation-auth-method-selection-and-session-timeout

## Why

The first implementation of in-conversation auth introduced `waiting_auth`, but the flow is still unstable:

- multi-method engines do not let the user explicitly choose an auth method first
- callback-style flows are misrepresented as authorization-code flows
- auth submission failures can be silent in chat UI
- auth timeout semantics are bound too loosely to run state instead of a concrete auth session
- frontend and backend timeout state can drift after reconnects

These issues make the current `waiting_auth` path hard to reason about and difficult to recover from safely.

## What Changes

This change refines the current in-conversation auth flow by:

1. requiring explicit auth method selection before creating an auth session when multiple methods are available
2. separating auth method from auth submission kind
3. treating timeout as auth-session-scoped instead of `waiting_auth`-scoped
4. exposing backend-authored auth session status/timeout data for frontend sync
5. making busy and submission failures explicit in chat UI

## Impact

- affects interactive run lifecycle, interactive job API, runtime event payloads, run persistence, and e2e chat UX
- does not introduce a new canonical runtime state beyond existing `waiting_auth`
- does not change headless behavior: non-conversation runs still fail with `AUTH_REQUIRED`
