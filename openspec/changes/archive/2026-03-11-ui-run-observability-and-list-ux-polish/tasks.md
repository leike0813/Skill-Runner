## 1. OpenSpec Artifacts

- [x] 1.1 Create proposal/design/tasks and delta specs for this change.

## 2. Bundle Download Split

- [x] 2.1 Add `GET /v1/jobs/{request_id}/bundle/debug` and keep normal bundle route unchanged.
- [x] 2.2 Add E2E proxy debug download endpoint and wire both buttons in run observe page.
- [x] 2.3 Ensure both download buttons are enabled only on `succeeded`.

## 3. Management Runs Pagination + Model

- [x] 3.1 Add `page/page_size` support in management runs query path with defaults.
- [x] 3.2 Return pagination metadata and model field in run list payload.
- [x] 3.3 Wire management UI + E2E runs pages to preserve pagination when opening detail and going back.

## 4. Run Detail UX Polish

- [x] 4.1 Add model display in run detail / run observe header.
- [x] 4.2 Add timeline attempt visual separators.
- [x] 4.3 Refresh management file tree on attempt change and terminal settle.
- [x] 4.4 Keep rebuild-protocol disabled on non-terminal statuses.

## 5. Preview + Text Rendering Polish

- [x] 5.1 Enable line numbers in highlighted previews.
- [x] 5.2 Fix JSON preview gray background contrast.
- [x] 5.3 Fix chat bubble wrapping to stay within bubble boundaries.
- [x] 5.4 Normalize timestamp rendering to browser local timezone.

## 6. Opencode Model Refresh UX

- [x] 6.1 Trigger opencode model catalog refresh after successful auth operations.
- [x] 6.2 Disable manual refresh button while request is in-flight and show refresh hint.

## 7. Docs & Validation

- [x] 7.1 Update `docs/api_reference.md` for new/updated APIs and payloads.
- [x] 7.2 Update i18n keys for all locales.
- [x] 7.3 Run targeted pytest suite and fix regressions.
