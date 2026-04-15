## 1. Protocol + Chat Replay

- [x] 1.1 Add backend display projection for `assistant.message.final` with additive `display_*` fields.
- [x] 1.2 Make chat replay derivation prefer `display_text` over raw `text`.
- [x] 1.3 Update runtime schema/invariants to describe the new projection behavior.

## 2. Frontend Alignment

- [x] 2.1 Update `e2e_client/templates/run_observe.html` so chat consumes `/chat` only, the pending card consumes `ui_hints`, and the final summary card is removed.
- [x] 2.2 Update `server/assets/templates/ui/run_detail.html` to render backend-projected chat text, including markdown final displays.

## 3. Documentation

- [x] 3.1 Update `docs/developer/frontend_design_guide.md` with the backend-driven structured-output display model.
- [x] 3.2 Add `artifacts/frontend_upgrade_guide_2026-04-15.md` describing the frontend migration and downgrade semantics.

## 4. Validation

- [x] 4.1 Update protocol/chat/frontend template guards.
- [x] 4.2 Run targeted pytest coverage for protocol + UI template changes.
- [x] 4.3 Run `openspec status --change backend-driven-structured-output-chat-alignment-2026-04-15 --json`.
- [x] 4.4 Run `openspec instructions apply --change backend-driven-structured-output-chat-alignment-2026-04-15 --json`.
- [x] 4.5 Run targeted mypy for the touched runtime/frontend-related Python modules.
