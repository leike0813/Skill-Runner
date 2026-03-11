## 1. OpenSpec Artifacts

- [x] 1.1 Create proposal/design/tasks and delta specs for this change.

## 2. Timezone Normalization

- [x] 2.1 Normalize run-related router datetime parsing to UTC-aware values before returning to UI clients.
- [x] 2.2 Ensure management run detail initial payload serializes timestamps with explicit timezone semantics.

## 3. Preview Rendering

- [x] 3.1 Add real `jsonl` detection and rendering in the file preview renderer.
- [x] 3.2 Generate line-numbered `rendered_html` for all non-Markdown displayable text previews.
- [x] 3.3 Keep Markdown rich rendering unchanged and exclude source line numbers.

## 4. Frontend Preview Consumption

- [x] 4.1 Update shared file explorer JS to always prefer backend `rendered_html` when available.
- [x] 4.2 Update management UI and E2E preview partials to match the new unified rendering behavior.
- [x] 4.3 Update time display scripts/templates to respect the corrected timezone payloads.

## 5. Validation

- [x] 5.1 Update or add targeted tests for timezone rendering assumptions and `jsonl`/line-number preview behavior.
- [x] 5.2 Run targeted pytest coverage for UI preview and route regressions.
