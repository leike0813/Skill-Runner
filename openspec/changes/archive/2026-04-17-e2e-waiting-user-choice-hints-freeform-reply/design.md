## Design

### Prompt card behavior

The prompt card continues to render all existing choice chips and file hints without changing the reply payload shape.

Clicking a chip still submits the current interaction response derived by `resolveInteractionActionResponse(...)`.

### Reply composer behavior

Composer visibility becomes independent from the presence of prompt-card choices.

- `kind === open_text`
  - keep the normal multi-line composer
  - placeholder still prefers `ui_hints.hint`, then the default reply placeholder
- `kind !== open_text`
  - keep all prompt-card action chips
  - keep the composer visible and enabled
  - switch the composer into a compact single-line visual mode
  - use a dedicated localized alternative placeholder

### Scope

This change is intentionally limited to:

- `e2e_client/templates/run_observe.html`
- e2e-facing locale strings
- e2e semantic tests
- `artifacts/frontend_upgrade_guide_2026-04-16_15-55-13.md`

No protocol, backend, or management UI changes are part of this work.
