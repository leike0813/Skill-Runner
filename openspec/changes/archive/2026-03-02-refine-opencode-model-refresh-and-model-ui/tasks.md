## 1. Catalog Refresh

- [x] 1.1 Make `OpencodeModelCatalog.start()` stop scheduling an implicit startup async refresh
- [x] 1.2 Await one `opencode` model refresh during `server.main` startup when startup probing is enabled
- [x] 1.3 Keep startup failure fallback non-blocking

## 2. UI Model Management

- [x] 2.1 Add a manual refresh action on `/ui/engines/opencode/models`
- [x] 2.2 Route manual refresh through `await opencode_model_catalog.refresh(...)`
- [x] 2.2a Refine manual refresh to use HTMX partial updates instead of full-page redirects
- [x] 2.3 Remove `display_name` column from the model management table
- [x] 2.4 Keep `opencode` model column display unchanged
- [x] 2.5 Show non-`opencode` display names in the `model` column
- [x] 2.6 Replace snapshot form `display_name` input with `model`

## 3. Verification

- [x] 3.1 Add/adjust UI tests for the manual refresh action and single-column model display
- [x] 3.1a Verify manual refresh returns an HTMX-refreshable partial response
- [x] 3.2 Add a startup test that asserts the `opencode` model refresh is awaited
- [x] 3.3 Run targeted mypy for modified production modules
