## Design Summary

The implementation keeps chat semantics unchanged and limits itself to frontend presentation and inspection behavior.

### Shared Markdown Pipeline

- Add a shared frontend renderer helper under `server/assets/static/js/` that encapsulates `markdown-it` plus `texmath + katex`.
- Add a shared scoped stylesheet under `server/assets/static/css/` for markdown body elements used inside chat bubbles and thinking/process items.
- Both the management run-detail page and the E2E observe page consume the same helper and stylesheet; neither page initializes its own standalone markdown parser anymore.

### Management Chat Inspector

- The management run-detail page adds a fixed right-side drawer and backdrop.
- Normal chat bubbles open the drawer when clicked.
- Thinking/process containers keep their expand/collapse behavior; each expanded child item gets a dedicated `View event` trigger that opens the same drawer.
- The drawer renders:
  - event meta (`role`, `kind`, `seq`, `attempt`, `created_at`)
  - correlation summary
  - full JSON event envelope
  - optional `raw_ref` preview jump button

### Data Source Boundary

- The inspector only shows the `chat-replay` event envelope already held by the page.
- No new backend endpoint is introduced.
- No FCMP cross-linking is added in this change.
