## 1. OpenSpec Artifacts

- [x] 1.1 Create change directory and proposal/design/tasks.
- [x] 1.2 Add delta specs for UI management and interactive job API.

## 2. Unified File Preview Rendering

- [x] 2.1 Add shared preview renderer service for text/binary/too_large detection.
- [x] 2.2 Add markdown safe render and json pretty render support.
- [x] 2.3 Extend preview payload with `detected_format` / `rendered_html` / `json_pretty`.
- [x] 2.4 Refactor skill browser preview and E2E bundle preview to reuse shared renderer.

## 3. UI Rendering Updates

- [x] 3.1 Fix E2E run preview panel scroll behavior for long content.
- [x] 3.2 Add markdown/json rendering branches to management and E2E file preview partials.
- [x] 3.3 Add FCMP/RASP/Orchestrator default summary bubbles in management run detail.
- [x] 3.4 Add per-panel `View raw` toggles and raw fallback rendering.

## 4. i18n and Dependencies

- [x] 4.1 Add locale keys required by new preview/protocol UI labels.
- [x] 4.2 Add `markdown` and `bleach` runtime dependencies.

## 5. Tests

- [x] 5.1 Add file preview renderer unit tests (markdown/json/binary/too_large).
- [x] 5.2 Update skill browser and E2E bundle preview tests for extended payload.
- [x] 5.3 Update E2E observe semantics tests for preview format and scroll behavior.
- [x] 5.4 Update management UI tests for protocol raw toggle and canonical chat title.
