## 1. Contracts & Models

- [x] 1.1 Add `upload_files` kind to ask_user contracts and runtime schema.
- [x] 1.2 Add ask_user file item model and include `files` in `AskUserHintPayload`.
- [x] 1.3 Add optional `ask_user` to `PendingAuth`.

## 2. Backend hard-cut to ask_user shape

- [x] 2.1 Refactor `AuthImportService.get_import_spec()` to return `ask_user` payload.
- [x] 2.2 Hard-cut management import spec response model to `ask_user` shape.
- [x] 2.3 Build import pending auth challenge with `ask_user.kind=upload_files`.

## 3. Frontend rendering convergence

- [x] 3.1 Update management UI import dialog to consume `ask_user.files`.
- [x] 3.2 Remove E2E hardcoded import spec and render from `pending_auth.ask_user`.
- [x] 3.3 Keep risk prompt rendering through `ask_user.ui_hints`.

## 4. Prompt/docs/tests

- [x] 4.1 Update interactive patch template + skill patch ask_user schema block.
- [x] 4.2 Update `docs/api_reference.md` import spec response example.
- [x] 4.3 Update unit tests for service/routes/orchestration/e2e semantics and run targeted pytest.
