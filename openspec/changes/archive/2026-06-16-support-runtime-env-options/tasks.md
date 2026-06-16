## 1. OpenSpec and Docs

- [x] 1.1 Validate the OpenSpec change artifacts.
- [x] 1.2 Add runtime env documentation under `docs/`.
- [x] 1.3 Update API and execution docs for `runtime_options.env`, redaction, cache behavior, and cleanup.

## 2. Validation and Secret Vault

- [x] 2.1 Add `env` to the runtime options policy allowlist.
- [x] 2.2 Validate env object shape, safe names, string values, value length, count, and protected names.
- [x] 2.3 Add a request-scoped runtime env secret service for validation, redaction, vault write/read, permissions, and cleanup.

## 3. API and Persistence

- [x] 3.1 Sanitize create/upload request runtime options before normal DB/API/audit persistence.
- [x] 3.2 Persist raw env only to the vault and redacted env projections to request/effective runtime options.
- [x] 3.3 Ensure request input snapshots and status/detail responses do not expose raw env values.

## 4. Execution

- [x] 4.1 Load runtime env from the vault during run attempt preparation and inject internal `__runtime_env`.
- [x] 4.2 Apply `__runtime_env` in the base execution adapter subprocess env without mutating `os.environ`.
- [x] 4.3 Fail attempts with `RUNTIME_ENV_SECRET_MISSING` when a declared env secret is unavailable.

## 5. Cache and Cleanup

- [x] 5.1 Keep runtime env out of cache key construction.
- [x] 5.2 Remove env secret files during expired run cleanup and manual cleanup.

## 6. Tests

- [x] 6.1 Add/extend options policy tests for valid env and validation failures.
- [x] 6.2 Add vault/redaction/permission tests.
- [x] 6.3 Add execution injection and no-global-mutation tests.
- [x] 6.4 Add regression tests for cache stability, retry/resume vault loading, cleanup, and raw env absence from DB/audit.
- [x] 6.5 Run targeted validation for changed areas.
