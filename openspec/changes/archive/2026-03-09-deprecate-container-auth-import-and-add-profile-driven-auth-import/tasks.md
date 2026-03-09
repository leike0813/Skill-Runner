## 1. Container Import Deprecation

- [x] 1.1 Remove `agent_config` mount from `docker-compose.yml` and `docker-compose.release.tmpl.yml`.
- [x] 1.2 Remove `/opt/config` import branch from `scripts/entrypoint.sh`.
- [x] 1.3 Remove `--import-credentials` CLI option and implementation from `scripts/agent_manager.py`.
- [x] 1.4 Update container and README docs to remove startup auto-import instructions.

## 2. Profile-Driven Import Contract

- [x] 2.1 Extend adapter profile schema with `credential_imports[].import_validator` and `aliases`.
- [x] 2.2 Extend adapter profile loader dataclasses/validation for the new fields.
- [x] 2.3 Update engine adapter profiles with validator declarations.

## 3. Import Service & Validators

- [x] 3.1 Add `auth_import_validator_registry` (declarative validator dispatch).
- [x] 3.2 Add `auth_import_service` (spec building + multipart import + writes).
- [x] 3.3 Implement OpenCode openai auth.json normalization (OpenCode/Codex format support).
- [x] 3.4 Implement OpenCode google provider checks and optional antigravity validation.

## 4. API & Runtime Flow

- [x] 4.1 Add management import spec endpoint.
- [x] 4.2 Add management import submit endpoint.
- [x] 4.3 Add `auth_method=import` to interaction/runtime contracts.
- [x] 4.4 Add jobs interaction auth import endpoint.
- [x] 4.5 Update auth orchestration to support import as conversation method and resume path.

## 5. UI Integration

- [x] 5.1 Update management engines auth menu to include import entries with separators.
- [x] 5.2 Add OpenCode provider-level import entry and google high-risk warning in dialog.
- [x] 5.3 Update E2E waiting_auth UI to handle `import` method with multipart upload flow.
- [x] 5.4 Add i18n keys in `en/zh/ja/fr`.

## 6. Docs & Validation

- [x] 6.1 Update `docs/api_reference.md` with all new import endpoints.
- [x] 6.2 Add/adjust unit tests for schema, service, routes, orchestration, and UI templates.
- [x] 6.3 Run targeted pytest + mypy and `openspec validate --change deprecate-container-auth-import-and-add-profile-driven-auth-import`.
