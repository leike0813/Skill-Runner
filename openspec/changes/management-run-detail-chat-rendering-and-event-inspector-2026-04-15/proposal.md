## Why

The management run-detail page currently carries a lighter markdown renderer than the built-in E2E client, which leads to visible formatting drift in chat and makes structured markdown content harder to read. The same page also lacks a first-class way to inspect the canonical chat event envelope behind each bubble, even though protocol and timeline panels already expose adjacent audit views.

This change aligns management chat rendering with the E2E frontend and adds a dedicated chat-event inspector without changing backend APIs.

## What Changes

- Move chat markdown rendering into shared frontend static assets used by both the management UI and the E2E observe client.
- Add a right-side chat inspector drawer to the management run-detail page for viewing raw `chat-replay` event envelopes.
- Keep `/chat` and `/chat/history` as the only data source for chat bubbles; the inspector reads the same event envelopes already returned to the page.

## Capabilities

### Modified Capabilities
- `web-management-ui`
- `builtin-e2e-example-client`
- `canonical-chat-replay`

## Impact

- Affected code: shared frontend markdown assets, management run-detail template, E2E observe template.
- Affected tests: UI template guards and management UI integration coverage.
