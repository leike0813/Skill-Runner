## Why

The backend now has a stable structured-output contract and same-attempt convergence model, but the frontend still carries display-side branching logic for pending/final JSON. That split is the wrong ownership boundary: it makes the UI responsible for protocol dispatch, encourages per-page drift, and duplicates logic between the E2E client and the management UI.

This change pulls structured-output display projection back into the backend so chat stays a single derived view and prompt cards stay a separate interaction view.

## What Changes

- Extend `assistant.message.final` with additive backend-projected display fields: `display_text`, `display_format`, `display_origin`, and optional `structured_payload`.
- Make canonical chat replay prefer `display_text` when present.
- Update the E2E client so chat consumes `/chat` only and the pending card consumes `ui_hints` only.
- Remove the E2E final summary card so final structured output is shown only in chat.
- Update the management run-detail page to render backend-projected chat text, including markdown final displays.
- Add documentation and upgrade guidance for frontend consumers.

## Capabilities

### Modified Capabilities
- `canonical-chat-replay`
- `interactive-job-api`
- `runtime-event-command-schema`
- `web-management-ui`
- `builtin-e2e-example-client`

## Impact

- Affected code: runtime protocol projection, chat replay derivation, E2E observe template, management run-detail template.
- Affected docs: `docs/developer/frontend_design_guide.md` and new `artifacts/frontend_upgrade_guide_2026-04-15.md`.
- Affected tests: runtime protocol/chat replay tests plus frontend template guards.
