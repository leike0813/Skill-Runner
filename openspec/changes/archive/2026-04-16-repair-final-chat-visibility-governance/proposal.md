# Proposal

## Why

In-attempt output repair currently allows multiple `assistant.message.final` events from the same repair chain to remain visible in chat. When an invalid final is immediately sent to the user and then superseded by a repair round, the chat window shows several "final" answers, including malformed structured payloads that should never remain primary-visible.

This degrades UX and makes chat replay unsuitable as a stable source for golden fixtures.

## What Changes

- Add a new public protocol event: `assistant.message.superseded`
- Introduce `message_family_id` for repair-chain final messages
- Define winner-only visibility for repair families
- Fold superseded final revisions out of the primary chat surface while preserving audit evidence
- Update chat replay derivation and management UI chat rendering to respect repair supersede mutations

## Impact

- Runtime protocol contracts and docs gain one new public event
- Chat replay/read-model gains revision mutation semantics
- Existing run states, waiting/auth precedence, and raw audit evidence remain unchanged
